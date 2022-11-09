import json
import yaml
import requests
import os
import re
from abc import ABC, abstractmethod
from functools import reduce
from time import sleep

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

# dump the dict of {path, 'htmlstring', ...} to single file
# adds a div with id of path, '/' replaced with '_'
def html_dict_to_file(html_dict, filepath):
  wrapper = ['<div id="{path_id}">\n', '</div>\n']

  with open(filepath, 'w') as output:
    for path, html in html_dict:
      path_id = re.sub('/', '_', path)
      output.write(wrapper[0].format(path_id = path_id))
      output.write(html)
      output.write('\n')
      output.write(wrapper[1])

if __name__ == '__main__':
  config = get_config()

  try:
    url = config['root_path']
  except KeyError as e:
    raise Exception('missing root_path var. please set and try again') from e

  try:
    config_filename = config['output_filename']
    output_path = config['output_path']
  except KeyError as e:
    raise Exception('missing output_filename or output_path var. please set and try again') from e

  space = gd.get_url(url)
  paths = gd.find_all_paths(space)
  data = gd.get_all_paths(paths, root_url = url)
  nodes = gd.pathdata_to_nodes(data)
  html = nodes_to_html(nodes)
  output_filepath = os.path.join(output_path, output_filename)
  html_dict_to_file(html, output_filepath)

class ElementTypes:
  types = [
    'paragraph',
    'heading-1',
    'heading-2', 
    'heading-3',
    'heading-4',
    'list-unordered',
    'list-ordered',
    'list-item',
    'text',
    'link',
    'table' # problematic
  ]

  tags = {
    'paragraph': ['<p{attribs}>', '</p>'],
    #'heading\-[1-6]+': ['<h\1', '</h\1>'],
    'heading-1': ['<h1{attribs}>', '</h1>'],
    'heading-2': ['<h2{attribs}>', '</h2>'],
    'heading-3': ['<h3{attribs}>', '</h3>'],
    'heading-4': ['<h4{attribs}>', '</h4>'],
    'heading-5': ['<h5{attribs}>', '</h5>'],
    'heading-6': ['<h6{attribs}>', '</h6>'],
    'list-unordered': ['<ul{attribs}>', '</ul>'],
    'list-ordered': ['<ol{attribs}>', '</ol>'],
    'list-item': ['<li{attribs}>', '</li>'],
    'text': ['', ''],
    'link': ['<a{attribs}>', '</a>'],
    'table': ['<table{attribs}>', '</table>']
  }

  attribs = {
    'ref': {'key': 'url', 'html_attrib': 'href'}
  }

class GitbookNode(ABC):
  
  @abstractmethod
  # get from nodes
  # return Node[]
  def get_children(self):
    pass

  @abstractmethod
  # look at type
  def is_text(self):
    pass

  @abstractmethod
  def is_inline(self):
    pass

  @abstractmethod
  def is_block(self):
    pass
  
  @abstractmethod
  def get_tags(self):
    pass

  @abstractmethod
  def outputstring(self):
    pass

class Node(GitbookNode):
  #data # dict of raw data 
  #children
  #node_type block, inline, etc
  #element_type paragraph, heading-1, etc
  #tags # list of [open_tag, close_tag]
  #marks # list of marks
  #depth # int from root (0)
  #attribs dict of attrib: value

  def __init__(self):
    self.children = []
    self.data = {}
    self.node_type = None
    self.tags = None
    self.marks = None
    self.depth = 0
    self.element_type = None
    self.attribs = {}
  
  # load the data from a data dict returned by gitbooks api
  # data dict is the response['document']
  # recursively adds children from nodes/leaves
  def loads(self, data, depth = 0):
    #print(f'node loads data: {data}')
    self.node_type = data['object']
    self.data = data
    if 'type' in data.keys():
      self.element_type = data['type']
    
    self.depth = depth
    child_depth = depth + 1

    self.set_tags()
    
    if isinstance(data, dict) and 'nodes' in data.keys():
      for node in data['nodes']:
        child = Node()
        child.loads(data = node, depth = child_depth)
        self.add_child(child)

    if isinstance(data, dict) and 'leaves' in data.keys():
      for leaf in data['leaves']:
        child = Leaf()
        child.loads(data = leaf, depth = child_depth)
        self.add_child(child)

  def get_children(self):
    return self.children

  def is_text(self):
    return self.node_type == 'text'

  def is_block(self):
    return self.node_type == 'block'

  def is_inline(self):
    return self.node_type == 'inline'

  def add_child(self, child):
    self.children.append(child)
    return self

  # set the attributes of the html element from
  # the 'data' dict 
  def set_attribs(self):
    # attributes appear to be held in 'data'
    # a dict of dicts for each attrib 
    # (e.g. 'ref': {'kind': 'url', 'url': 'http...'})
    if 'data' in self.data.keys():
      for key, attrib in self.data['data'].items():
        try:
          lookup = ElementTypes.attribs[key]
          value = attrib[lookup['key']]
          self.attribs[lookup['html_attrib']] = value
        except KeyError:
          print(f'missing in {self.data["data"]}')
          pass
    return self

  # get a string representation of the attributes for 
  # subtitution into tag
  def get_attrib_string(self):
    return ' '.join([f'{k}="{v}"' for k, v in self.attribs.items()])

  # set the start and end tags in self.tags
  # calls the set_attribs method to add attributes from 
  # 'data' and then creates the correctly formatted tag
  def set_tags(self):
    # make sure we have empty tags if no element_type set
    # otherwise, lookup tags from ElementTypes.tags
    if self.element_type == None:
      self.tags = ['', '']
    else:
      #poss_tags = [re.sub(i[0], i[1], self.element_type) for i in ElementTypes.tags.items() if re.match(i[0], self.element_type)]
      self.tags = ElementTypes.tags[self.element_type]

    # insert the attributes from self.attribs dict
    self.set_attribs()
    attribs = ''
    if len(self.attribs.keys()) > 0:
      attribs = self.get_attrib_string()
      attribs = f' {attribs}'
    self.tags[0] = self.tags[0].format(attribs = attribs)

    return self

  def get_tags(self):
    return self.tags

  def outputstring(self):
    childoutput = ''.join(list(map(lambda c: c.outputstring(), self.children)))
    end_chars = '\n' if self.node_type == 'block' else ''
    return f'{self.tags[0]}{childoutput}{self.tags[1]}{end_chars}'

# Leaf class
# similar to Node but for text only
# tags are built from marks, objects representing <em>, <strong>, etc
class Leaf(Node):
  #text
  #tags
  #marks
  mark_tag = {
    'italic': ['<em>', '</em>'],
    'strong': ['<strong>', '</strong>'],
    'bold': ['<strong>', '</strong>'],
    'underline': ['<u>', '</u>']
  }

  def __init__(self):
    super().__init__()
    self.tags = []
    self.marks = []
    self.text = ''
    self.children = None

  def get_children():
    raise TypeError('Leaf object has no children')

  def loads(self, data, depth = 0):
    self.node_type = data['object']
    if 'type' in data.keys():
      self.element_type = data['type']
    
    self.text = data['text']
    self.depth = depth

    # marks contains objects representing <em> etc
    # these are added to the tags and then compiled by set_tags
    for mark in data['marks']:
      self.add_tag(mark)

    self.set_tags()
    return self

  def add_tag(self, mark):
    mark = self.mark_tag[mark['type']]
    self.marks.append(mark)
    return self

  def set_tags(self):
    opening = reduce(lambda text, m: f'{text}{m[0]}', self.marks, '')
    closing = reduce(lambda text, m: f'{text}{m[1]}', reversed(self.marks), '')
    self.tags = [opening, closing]
    return self

  def outputstring(self):
    return f'{self.tags[0]}{self.text}{self.tags[1]}'
