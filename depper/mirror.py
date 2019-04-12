import functools
import io
import json
import packaging
import tarfile
import zipfile

from pypi_simple import PyPISimple
import requests

class MissingFilesError(Exception):

    def __init__(self, package, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.package = package

class MissingSetupError(Exception):
    pass

class MissingManifestError(Exception):
    pass

class PyPiClient:

    def __init__(self, cache_path:"str"):
        self.client = PyPISimple()
        self.session = requests.Session()
        self.cache_path = cache_path
        
    @functools.lru_cache(maxsize=2)
    def list_projects(self):
        try:
            return self.load_cached_mirror()
        except:
            return list(self.client.get_projects())

    def new_projects(self):
        cached_projects = set(self.load_cached_mirror())
        found_projects = set(self.list_projects())

        return set.difference(cached_projects, found_projects) 

    def download_mirror(self):
        projects = self.list_projects()

        with open(self.cache_path, 'w', encoding='utf-8-sig') as f:
            json.dump(projects, fp=f)

    def load_cached_mirror(self):
        with open(self.cache_path, 'r', encoding='utf-8-sig') as f:
            doc = json.load(fp=f)
        return doc

    @functools.lru_cache(maxsize=20)
    def extract_latest_project_file(self, project):
        project_files = self.client.get_project_files(project)
        max_version = packaging.version.parse('-1')
        max_file = None
        for project_file in project_files:
            if project_file.version is None:
                version = packaging.version.parse('0.0.0')
            else:
                version = packaging.version.parse(project_file.version)
            if project_file.package_type in ('sdist', 'wheel') and (version > max_version or (version == max_version) and project_file.package_type == 'wheel'):
                max_file, max_version = project_file, version
        if not max_file:
            raise MissingFilesError('Missing files?')
        return max_version, max_file

    @functools.lru_cache(maxsize=20)
    def extract_setup_py(self, project):
        version, project_file = self.extract_latest_project_file(project)
        response = self.session.get(project_file.url, stream=True, timeout=10)
        fp = io.BytesIO(response.content)

        if project_file.filename.endswith('.zip') or project_file.filename.endswith('.whl'):
            zf = zipfile.ZipFile(fp)
            if project_file.filename.endswith('.zip'):
                nameinfos = list([ni for ni in zf.namelist() if ni.endswith('/setup.py')])
                if nameinfos:
                    return ('setup.py', version, zf.read(nameinfos[0]))
                raise MissingSetupError()
            else:
                nameinfos = list([ni for ni in zf.namelist() if ni.endswith('/METADATA')])
                if nameinfos:
                    return ('metadata', version, zf.read(nameinfos[0]))
                raise MissingManifestError()
        else:
            tf = tarfile.open(fileobj = fp)
            nameinfos = list(ni for ni in tf.getnames() if ni.endswith('/setup.py'))
            if nameinfos:
                data = tf.extractfile(nameinfos[0])
                return ('setup.py', version, data.read())
            raise MissingSetupError()

def save_data(file_path, data):
    import os
    try:
        os.replace(file_path, file_path + '.old')
    except Exception:
        pass
    with open(file_path, 'w') as f:
        json.dump(data, f)
    
client = PyPiClient('./projects.json')
# client.download_mirror()

data_file = './setupinfo.json'

try:
    with open(data_file, 'r') as f:
        data = json.load(f, encoding='utf-8-sig')
except FileNotFoundError:
    save_data(data_file, {})
    data = {}

for project in client.list_projects():
    if project not in data:
        try:
            (metadata_type, version, contents) = client.extract_setup_py(project)
            info = {
                'type': metadata_type,
                'content': contents.decode('utf-8-sig') 
            }
            data[project] = info
            print('.', end='')
        except UnicodeDecodeError as ude:
            data[project] = {
                'type': 'UnicodeDecodeError',
                'content': str(ude)
            }
            print('U', end='')
        except MissingManifestError:
            data[project] = {
                'type': 'MissingManifestError',
                'content': '*** No MANIFEST in whl'
            }
            print('X', end='')
        except MissingSetupError:
            data[project] = {
                'type': 'MissingSetupError',
                'content': '*** No setup in sdist'
            }
            print('S', end='')
        except MissingFilesError:
            data[project] = {
                'type': 'MissingFilesError',
                'content': '*** No SDIST or whl in pkg'
            }
            print('M', end='')
        except tarfile.ReadError:
            data[project] = {
                'type': 'tarfile.ReadError',
                'content': '*** Failed to read Tarfile?'
            }
            print('R', end='')
        except Exception as e:
            data[project] = {
                'type': 'UnknownError',
                'content': '*** Error {}'.format(str(e))
            }
            print('?', end='')
        data[project]['version'] = str(version)
        if len(data) % 1000 == 0:
            print('\n')
            print(len(data), end='')
            save_data(data_file, data)

save_data(data_file, data)
