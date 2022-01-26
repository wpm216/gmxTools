
# Super simple object that stores each group's indices in a dictionary.
# TODO: add support for file writing.

import os
from fileParser import File
from .misc import AttributeDict, flatten2d

  
  def __init__(self, path = None,  *args, **kwargs):

    if not type(path) is str:
      raise TypeError("Path must be a str type, not {}".format(type(path)))

    self.path = path
    self.name = os.path.splitext(os.path.basename(path))[0]

    if self.path:
      self.load()

    self.update(*args, **kwargs)

  def load(self):
    assert os.path.isfile(self.path), "No file found at path {}".format(self.path)

    tf = lambda x: [int(i) for i in x.strip("\n").split()]
    with File(self.path) as f:
      # advance to the first group's header
      f.advance_to("\[", junk = ["^;", "^\n"], quiet = True)
      while not f.eof:
        # store the header as a key
        key = f.cl.split("[")[1].split("]")[0].replace(" ", "")
        # get the indices as values
        data = f.advance_to("\[", junk = ["^;", "^\n"], hold_all = True, quiet = True, tf = tf, exclude = True)
        # format it as a list of integers
        indices = flatten2d(data)
        # store as a key, val pair
        self[key] = indices

