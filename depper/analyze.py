import json

def _extract_install_requires_setup(contents):
    index = contents.find('install_requires')
    if index == -1:
        return ''
    left = contents.find('[', index)
    right = contents.find(']', left)
    return contents[left:right + 1]

def _extract_install_requires_metadata(contents):
    requires_dist_lines = [line for line in contents.splitlines() if 'Requires-Dist:' in line]
    return '\n'.join(requires_dist_lines)
        
def extract(cache):
    with open(cache, 'r', encoding='utf-8-sig') as f:
        doc = json.load(f)
    for project, data in doc.items():
        if data['type'] == 'setup.py':
            setup_content = data['contents']
            install_requires = _extract_install_requires_setup(setup_content)
            if 'azure-' in install_requires:
                print(project)
        elif data['type'] == 'metadata':
            metadata_content = data['contents']
            install_requires = _extract_install_requires_metadata(metadata_content)
            if 'azure-' in install_requires:
                print(project)
