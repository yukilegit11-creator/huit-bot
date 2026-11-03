
import fbchat_muqit, inspect, os
pkg_path = os.path.dirname(inspect.getfile(fbchat_muqit))
print('Package path:', pkg_path)
for root, dirs, files in os.walk(pkg_path):
    for f in files:
        if f.endswith('.py'):
            fp = os.path.join(root, f)
            with open(fp, 'r', encoding='utf-8', errors='ignore') as code_f:
                content = code_f.read()
                if 'async_get_token' in content:
                    print(f'Found async_get_token in {fp}')
