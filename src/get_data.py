import json
import yaml
import requests
import os
import re
from abc import ABC, abstractmethod
from functools import reduce

# https://api.gitbook.com/v1/spaces/{space_id}/
# https://api.gitbook.com/v1/spaces/{space_id}/content/
# https://api.gitbook.com/v1/spaces/{space_id}/content/page/{page_id}
#

def get_api_key():
  api_key = os.getenv('GITBOOK_API')

  if api_key == None:
    print('Using config as no GITBOOK_API env var present')

    with open('config.yaml') as config_file:
      config = yaml.load(config_file)

    try:
      api_key = config['GITBOOK_API']
    except KeyError as e:
      raise Exception('missing GITBOOK_API var. please set and try again') from e

  return api_key

def test(url):
  api_key = get_api_key()

  r = requests.get(url, headers = {'Authorization': f'Bearer {api_key}'})
  data = r.json()
  root = Node()
  root.loads(data['document'], 0)

  return root

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
    'link'
  ]

  tags = {
    'paragraph': ['<p>', '</p>'],
    #'heading\-[1-6]+': ['<h\1', '</h\1>'],
    'heading-1': ['<h1>', '</h1>'],
    'heading-2': ['<h2>', '</h2>'],
    'heading-3': ['<h3>', '</h3>'],
    'heading-4': ['<h4>', '</h4>'],
    'heading-5': ['<h5>', '</h5>'],
    'heading-6': ['<h6>', '</h6>'],
    'list-unordered': ['<ul>', '</ul>'],
    'list-ordered': ['<ol>', '</ol>'],
    'list-item': ['<li>', '</li>'],
    'text': ['', ''],
    'link': ['<a{attrib}>', '</a>'],
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
  #node_type
  #tags # list of [open_tag, close_tag]
  #marks # list of marks
  #depth # int from root (0)

  def __init__(self):
    self.children = []
    self.data = {}
    self.node_type = None
    self.tags = None
    self.marks = None
    self.depth = 0
    self.element_type = None
  
  def loads(self, data, depth = 0):
    self.node_type = data['object']
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

  def set_tags(self):
    if self.element_type == None:
      self.tags = ['', '']
    else:
      #poss_tags = [re.sub(i[0], i[1], self.element_type) for i in ElementTypes.tags.items() if re.match(i[0], self.element_type)]
      self.tags = ElementTypes.tags[self.element_type]
    return self

  def get_tags(self):
    return self.tags

  def outputstring(self):
    print(self.element_type)
    print(self.tags)
    childoutput = '\n'.join(list(map(lambda c: c.outputstring(), self.children)))
    return f'{self.tags[0]}{childoutput}{self.tags[1]}'

class Link(Node):

  def __init__(self):
    super().__init__()
    self.tags = ElementTypes.tags['link']
    self.url = ''

  def add_url(self):
    self.url = self.data['ref']['url']
    self.tags[0] = self.tags[0].format(attrib = f'href="{self.url}"')

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
    print(data)
    self.node_type = data['object']
    if 'type' in data.keys():
      self.element_type = data['type']
    
    self.text = data['text']
    self.depth = depth
    for mark in data['marks']:
      self.add_tag(mark)

    self.set_tags()
    return self

  def add_tag(self, mark):
    mark = self.mark_tag[mark['type']]
    self.marks.append(mark)
    return self

  def set_tags(self):
    opening = reduce(lambda text, m: f'{t}{m[0]}', self.marks, '')
    closing = reduce(lambda text, m: f'{t}{m[1]}', self.marks, '')
    self.tags = [opening, closing]
    return self

  def outputstring(self):
    print(self.element_type)
    print(self.tags)
    return f'{self.tags[0]}{self.text}{self.tags[1]}'
