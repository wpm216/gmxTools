from collections import OrderedDict

# miscellaneous objects and methods used in other parts of the code

def flatten2d(l):
  """ Returns a flattened version of a list of lists. """
  try:
    test = l[0][0]
    return [item for sublist in l for item in sublist]
  except TypeError:
    return l

class AttributeDict(OrderedDict):

  # AttributeDict code from AiiDA:
  #  https://github.com/aiidateam/aiida-core/blob/develop/aiida/common/extendeddicts.py
  
  """
  This class internally stores values in a dictionary, but exposes
  the keys also as attributes, i.e. asking for attrdict.key
  will return the value of attrdict['key'] and so on.
  Raises an AttributeError if the key does not exist, when called as an attribute,
  while the usual KeyError if the key does not exist and the dictionary syntax is
  used.
  """

  def __init__(self, dictionary=None):
    """Recursively turn the `dict` and all its nested dictionaries into `AttributeDict` instance."""
    super().__init__()
    if dictionary is None:
      dictionary = {}

    for key, value in dictionary.items():
      if isinstance(value, Mapping):
        self[key] = AttributeDict(value)
      else:
        self[key] = value

  def __repr__(self):
    """Representation of the object."""
    return '%s(%s)' % (self.__class__.__name__, dict.__repr__(self))


  def __getattr__(self, key):
    try:
      return self[key]
    except KeyError:
      errmsg = "'{}' object has no attribute '{}'".format(self.__class__.__name__, key)
      raise AttributeError(errmsg)
      
  def __setattr__(self, key, val):
    try:
      self[key] = val
    except KeyError:
      errmsg = "'{}' object has no attribute '{}'".format(self.__class__.__name__, key)
      raise AttributeError(errmsg)
    
  def __delattr__(self, key):
    try:
      del self[key]
    except KeyError:
      errmsg = "'{}' object has no attribute '{}'".format(self.__class__.__name__, key)
      raise AttributeError(errmsg)

  def __deepcopy__(self, memo=None):
    """Deep copy."""
    from copy import deepcopy

    if memo is None:
      memo = {}
    retval = deepcopy(dict(self))
    return self.__class__(retval)

  def __getstate__(self):
    """Needed for pickling this class."""
    return self.__dict__.copy()

  def __setstate__(self, dictionary):
    """Needed for pickling this class."""
    self.__dict__.update(dictionary)

  def __dir__(self):
    return self.keys()


