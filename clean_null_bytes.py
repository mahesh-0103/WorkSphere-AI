import os

folder = 'backend'
for root, dirs, files in os.walk(folder):
    for f in files:
        if f.endswith('.py'):
            path = os.path.join(root, f)
            with open(path, 'rb') as file:
                content = file.read()
            if b'\x00' in content:
                print(f'Null bytes found in: {path}')
                try:
                    text = content.decode('utf-16')
                    print('  Decoded as UTF-16')
                except:
                    text = content.replace(b'\x00', b'').decode('utf-8', errors='ignore')
                    print('  Stripped null bytes manually')
                
                with open(path, 'w', encoding='utf-8') as outfile:
                    outfile.write(text)
                print(f'  Fixed: {path}')
print("Done")
