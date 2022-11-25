import json
import yaml
import requests
import os
import re
from time import sleep
from GitbookNode import ElementTypes, Node, Leaf

# https://api.gitbook.com/v1/spaces/{space_id}/
# https://api.gitbook.com/v1/spaces/{space_id}/content/
# https://api.gitbook.com/v1/spaces/{space_id}/content/page/{page_id}
#

def get_api_key():
  api_key = os.getenv('GITBOOK_API')

  if api_key == None:
    print('Using config as no GITBOOK_API env var present')

    config = get_config()

    try:
      api_key = config['GITBOOK_API']
    except KeyError as e:
      raise Exception('missing GITBOOK_API var. please set and try again') from e

  return api_key

def get_config():
  with open('config.yaml') as config_file:
    config = yaml.load(config_file)

  return config

def get_url(url):
  api_key = get_api_key()
  r = requests.get(url, headers = {'Authorization': f'Bearer {api_key}'})
  return r.json()

def find_all_paths(content):
  paths = []
  if 'path' in content.keys():
    paths.append(content['path'])
  if 'pages' in content.keys():
    for page in content['pages']:
      paths = paths + find_all_paths(page)
  return paths

# get all paths in list of paths provided
# root_url must be in format https://api.gitbook.com/v1/spaces/{space_id}/content
def get_all_paths(paths, root_url):
  data = {}
  for path in paths:
    print(f'Getting path {path}')
    encoded_path = requests.utils.quote(path, safe = '')
    url = f'{root_url}/path/{encoded_path}'
    data[path] = get_url(url)
    # wait for a second to stop hammering server
    sleep(0.5)

  return data

# process dict of {path: jsondata, ...}
# return dict of {path: Node, ...}
def pathdata_to_nodes(data):
  nodes = {}
  for path, pathdata in data.items():
    if 'document' not in pathdata.keys():
      print(f'Skipping {path} as no "document" key')
    else:
      node = Node()
      node.loads(pathdata['document'])
      nodes[path] = node 
  return nodes

# process dict of {path: Node, ...}
# return dict of {path: 'htmlstring', ...}
def nodes_to_html(nodes):
  htmls = {}
  for path, node in nodes.items():
    htmls[path] = node.outputstring()
  return htmls

def test(url = ''):
  api_key = get_api_key()

  r = requests.get(url, headers = {'Authorization': f'Bearer {api_key}'})
  data = r.json()
  root = Node()
  root.loads(data['document'], 0)

  return root

def get_id_list(html_dict):
  id_list = []
  for path, html in html_dict.items():
    path_id = re.sub('/', '_', path)
    id_list.append(path_id) 

  return id_list

# convert the dict of {path, 'htmlstring', ...} to single string
def html_dict_to_html_string(html_dict, wrapper = ['<div id="{path_id}">\n', '</div>\n']):
  html_string = ''
  for path, html in html_dict.items():
    path_id = re.sub('/', '_', path)
    opening_tag = wrapper[0].format(path_id = path_id)
    html_string = f'{html_string}{opening_tag}{html}\n'
    html_string = f'{html_string}{wrapper[1]}'

  return html_string

# convert the dict of {path, 'htmlstring', ...} to
# component with x-data and x-show on each node
def html_dict_to_component_string(html_dict, wrapper = ['<div x-data="{}">', '</div>'], component_wrapper = ['<div>', '</div>'], header = ''):

  html_inner_string = html_dict_to_html_string(html_dict, wrapper = wrapper)
  
  return f'{header}{component_wrapper[0]}\n{html_inner_string}\n{component_wrapper[1]}'

# dump the dict of {path, 'htmlstring', ...} to single file
# adds a div with id of path, '/' replaced with '_'
def html_dict_to_file(html_dict, filepath, wrapper = ['<div id="{path_id}">\n', '</div>\n']):
  id_list = []

  with open(filepath, 'w') as output:
    for path, html in html_dict.items():
      path_id = re.sub('/', '_', path)
      # add id to id_list for later writing
      id_list.append(path_id) 
      output.write(wrapper[0].format(path_id = path_id))
      output.write(html)
      output.write('\n')
      output.write(wrapper[1])

  print(f'Written output to {filepath}')

  with open(f'{filepath}.ids', 'w') as f:
    for path_id in id_list:
      f.writelines(f'{path_id}\n')
  print(f'Written id list to {filepath}.ids')

# dump the string representation of the data to filepath
# and the id_list list of ids to filepath.ids
def dump_to_file(html_string, id_list, filepath):
  with open(filepath, 'w') as output:
    output.write(html_string)
  print(f'Written output to {filepath}')

  with open(f'{filepath}.ids', 'w') as f:
    for path_id in id_list:
      f.writelines(f'{path_id}\n')
  print(f'Written id list to {filepath}.ids')
  
if __name__ == '__main__':
  config = get_config()

  try:
    url = config['root_path']
  except KeyError as e:
    raise Exception('missing root_path var. please set and try again') from e

  try:
    output_filename = config['output_filename']
    output_path = config['output_path']
  except KeyError as e:
    raise Exception('missing output_filename or output_path var. please set and try again') from e

  space = get_url(url)
  paths = find_all_paths(space)
  print(f'Found paths: {paths}')
  data = get_all_paths(paths, root_url = url)
  nodes = pathdata_to_nodes(data)
  html_dict = nodes_to_html(nodes)
  id_list = get_id_list(html_dict)

  # now convert the html dict of {path_id: 'htmlstring', ...} to
  # a component
  #
  # first setup header and wrappers for each section
  header = '''
    <script>
        function data() {
            return {
                base_path: @entangle('base_path'),
                get help_section() {
                    return this.base_path == '' ? this.help_subsection : this.base_path+'_'+this.help_subsection;
                }
            }
        }
    </script>
    '''
  component_wrapper = [r'''<div x-data="data()">''', '</div>']  
  wrapper = [
    '<div x-show="help_section == \'{path_id}\'">\n',
    '</div>\n'
  ]
  # get the component string
  component_string = html_dict_to_component_string(html_dict, wrapper = wrapper, component_wrapper = component_wrapper, header = header) 
  output_filepath = os.path.join(output_path, output_filename)
  print(f'Dumping to file {output_filepath}')
  dump_to_file(component_string, id_list, output_filepath)

