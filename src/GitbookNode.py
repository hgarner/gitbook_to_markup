from abc import ABC, abstractmethod
from functools import reduce

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
  # get a list of [openingtag, closingtag]
  def get_tags(self):
    pass

  @abstractmethod
  # return string representation of self and all child nodes
  def outputstring(self):
    pass

  @abstractmethod
  # import data from dict returned by gitbooks api
  # add children from 'nodes' and 'leaves'
  def loads(self):
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

# Default extends dict class to return 'auto' as a value if key missing
# used for attribs so they have default values
class AutoDefault(dict):
  def __missing__(self, key):
    return 'auto'

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
    'underline': ['<u>', '</u>'],
  }

  style_tag = {
    'color': ['<span style="color: {text}; background-colour: {background}">', '</span>'],
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
    # tag may be in mark_tag or in style_tag, so check both
    try:
      mark_tags = self.mark_tag[mark['type']]
    except KeyError:
      mark_tags = self.style_tag[mark['type']]
      # apply the style to the span
      # note that the AutoDefault dict extension is used
      # to replace missing attribs with 'auto'
      mark_data = AutoDefault(mark['data'])
      mark_tags[0] = mark_tags[0].format_map(mark_data)
    self.marks.append(mark_tags)
    return self

  def set_tags(self):
    opening = reduce(lambda text, m: f'{text}{m[0]}', self.marks, '')
    closing = reduce(lambda text, m: f'{text}{m[1]}', reversed(self.marks), '')
    self.tags = [opening, closing]
    return self

  def outputstring(self):
    return f'{self.tags[0]}{self.text}{self.tags[1]}'
