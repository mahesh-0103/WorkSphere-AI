class SharedContext:
    def __init__(self, user_query: str = None):
        self.user_query = user_query
        self.email_results = None
        self.meeting_results = None
        self.task_results = None
        self.research_results = None
        self.report = None
        self.structured = None

    def reset(self):
        """
        Resets all variables to None.
        """
        self.user_query = None
        self.email_results = None
        self.meeting_results = None
        self.task_results = None
        self.research_results = None
        self.report = None
        self.structured = None

    def to_dict(self) -> dict:
        """
        Returns all properties as a dictionary.
        """
        return {
            "user_query": self.user_query,
            "email_results": self.email_results,
            "meeting_results": self.meeting_results,
            "task_results": self.task_results,
            "research_results": self.research_results,
            "report": self.report,
            "structured": self.structured
        }
