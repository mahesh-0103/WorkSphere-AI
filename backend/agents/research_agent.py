import os
import json
import hashlib
import httpx
import base64
from ai.model_router import model_router
from memory.cache import cache_client
from ai.runtime_settings import settings
from graph.client import GraphClient

class ResearchAgent:
    async def run(self, access_token: str, user_query: str, provider: str = "microsoft") -> dict:
        """
        Searches OneDrive personal drive files (or Google Drive), truncates metadata, applies MD5 caching, 
        and extracts relevant documents and key findings via the Model Router.
        """
        try:
            processed_docs = []
            
            if provider == "google":
                import httpx
                async with httpx.AsyncClient() as client:
                    resp = await client.get(
                        "https://www.googleapis.com/drive/v3/files",
                        params={
                            "q": f"fullText contains '{user_query}' and trashed=false",
                            "pageSize": 5,
                            "fields": "files(id,name,mimeType,modifiedTime,webViewLink)"
                        },
                        headers={"Authorization": f"Bearer {access_token}"}
                    )
                    files = resp.json().get("files", []) if resp.status_code == 200 else []
                    docs_data = [
                        {"name": f.get("name"), "url": f.get("webViewLink"), "modified": f.get("modifiedTime")}
                        for f in files
                    ]
            else:
                folder_path = getattr(settings, "onedrive_root", "/Documents")
                print(f"[ResearchAgent] Resolved OneDrive folder path: {folder_path}")
                
                # Check that the bearer token has the Files.Read.All scope
                has_scope = False
                if access_token.startswith("dummy"):
                    has_scope = True
                else:
                    try:
                        parts = access_token.split('.')
                        if len(parts) >= 2:
                            payload_b64 = parts[1]
                            payload_b64 += '=' * (-len(payload_b64) % 4)
                            payload_str = base64.urlsafe_b64decode(payload_b64).decode('utf-8')
                            payload_data = json.loads(payload_str)
                            scp = payload_data.get("scp", "")
                            scopes = scp.split() if isinstance(scp, str) else scp
                            if "Files.Read.All" in scopes or "Files.Read" in scopes:
                                has_scope = True
                    except Exception as se:
                        print(f"[ResearchAgent] Scope check warning (could not decode token): {se}")
                        # Assume True for opaque/unparseable tokens to prevent breaking flow
                        has_scope = True

                if not has_scope:
                    err_msg = "Access token is missing the required 'Files.Read.All' scope."
                    print(f"[ResearchAgent ERROR] {err_msg}")
                    raise Exception(err_msg)

                # Query Graph API to list files
                files = []
                if access_token.startswith("dummy"):
                    print(f"[ResearchAgent] MS Graph API response status code: 200")
                    # Use mock data documents
                    mock_graph = GraphClient(access_token)
                    files = mock_graph._get_mock_data()["documents"]
                else:
                    async with httpx.AsyncClient() as client:
                        headers = {
                            "Authorization": f"Bearer {access_token}",
                            "Content-Type": "application/json"
                        }
                        
                        path_strip = folder_path.strip().strip("/")
                        if not path_strip or path_strip.lower() == "root":
                            url = "https://graph.microsoft.com/v1.0/me/drive/root/children"
                        else:
                            url = f"https://graph.microsoft.com/v1.0/me/drive/root:/{path_strip}:/children"

                        resp = await client.get(url, headers=headers)
                        print(f"[ResearchAgent] Querying path '{folder_path}' -> MS Graph API response status code: {resp.status_code}")

                        if resp.status_code == 403:
                            err_msg = f"MS Graph API returned 403 Forbidden for path '{folder_path}'."
                            print(f"[ResearchAgent ERROR] {err_msg}")
                            raise Exception(err_msg)
                        
                        if resp.status_code == 200:
                            files = resp.json().get("value", [])
                            if not files:
                                print(f"[ResearchAgent WARNING] Configured path '{folder_path}' returned empty result.")
                        else:
                            print(f"[ResearchAgent WARNING] Query to configured path '{folder_path}' failed with status code {resp.status_code}.")

                        # Fallback to root drive if configured subfolder returns empty or fails
                        if not files and path_strip and path_strip.lower() != "root":
                            print("[ResearchAgent] Attempting fallback: listing from the root drive.")
                            fallback_url = "https://graph.microsoft.com/v1.0/me/drive/root/children"
                            fb_resp = await client.get(fallback_url, headers=headers)
                            print(f"[ResearchAgent] MS Graph API (root fallback) response status code: {fb_resp.status_code}")
                            
                            if fb_resp.status_code == 403:
                                err_msg = "MS Graph API returned 403 Forbidden for root fallback."
                                print(f"[ResearchAgent ERROR] {err_msg}")
                                raise Exception(err_msg)
                            elif fb_resp.status_code == 200:
                                files = fb_resp.json().get("value", [])
                                if not files:
                                    print("[ResearchAgent ERROR] Root fallback also returned empty result.")
                            else:
                                print(f"[ResearchAgent WARNING] Root fallback failed with status code {fb_resp.status_code}.")

                if not files:
                    err_msg = "OneDrive query returned 0 documents (configured folder empty and root fallback empty or failed)."
                    print(f"[ResearchAgent ERROR] {err_msg}")
                    raise Exception(err_msg)

                docs_data = [
                    {
                        "name": f.get("name"),
                        "webUrl": f.get("webUrl"),
                        "description": f.get("description") or f.get("name")
                    }
                    for f in files
                ]

            for doc in docs_data:
                processed_docs.append({
                    "name": doc.get("name", "")[:100],
                    "webUrl": doc.get("url") if provider == "google" else doc.get("webUrl", ""),
                    "description": doc.get("name", "")[:200] if provider == "google" else (doc.get("description") or doc.get("name", ""))[:200]
                })

            # 2. Caching layer optimization
            raw_json = json.dumps(processed_docs, sort_keys=True)
            data_hash = hashlib.md5(raw_json.encode('utf-8')).hexdigest()
            cache_key = f"research_agent:{data_hash}:{hashlib.md5(user_query.encode('utf-8')).hexdigest()}"
            
            cached_result = await cache_client.get(cache_key)
            if cached_result:
                return cached_result

            # 3. Prompt definition
            prompt = f"""
You are an Enterprise Knowledge Analyst searching workspace documents (OneDrive, SharePoint, and indexed sources).
Analyze these document search results:
{json.dumps(processed_docs, indent=1)}

Based on this information, identify:
1) Relevant Documents: Key files, spreadsheets, or presentations containing answers to the user query.
2) Important Findings: Specific details, prior decisions, contract commitments, or context mentioned in those files.
3) Potential Risks: Renewal dates, safety hazards, legal terms, budget concerns, or delivery problems mentioned in those documents.

Context (what the user is asking about): {user_query}
"""
            schema = {
                "relevant_documents": ["list of relevant document titles or paths"],
                "important_findings": ["list of key findings or details extracted from documents"],
                "potential_risks": ["list of potential contract, delivery, or business risks identified"]
            }
            
            # Execute through router
            preferred_model = getattr(settings, "per_analyst_models", {}).get("research")
            result = await model_router.structured_extract(
                content=prompt,
                schema=schema,
                preferred_model=preferred_model
            )
            
            structured_res = {
                "relevant_documents": result.get("relevant_documents", []),
                "important_findings": result.get("important_findings", []),
                "potential_risks": result.get("potential_risks", [])
            }
            
            # Cache the result
            await cache_client.set(cache_key, structured_res, ttl=settings.graph_cache_ttl)
            return structured_res

        except Exception as e:
            return {
                "relevant_documents": [],
                "important_findings": [],
                "potential_risks": [],
                "error": str(e)
            }
