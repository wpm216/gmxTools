
# A first hack at a GROMACS mdp filetype
# Its a glorified dictionary that can write itself to a file, at this point.

import os
from fileParser import File
from .misc import AttributeDict

class mdp(AttributeDict):
  
  def __init__(self, path = None,  *args, **kwargs):

    if not type(path) is str:
      raise TypeError("Path must be a str type, not {}".format(type(path)))

    self.path = path
    self.name = os.path.splitext(os.path.basename(path))[0]

    if self.path:
      self.load(path)

    self.update(*args, **kwargs)
    
  def __repr__(self):
    return "GMX MDP file: {}".format(self.name.upper())

  def write(self, path):

    if os.path.dirname(path) and not os.path.isdir(os.path.dirname(path)):
      os.makedirs(os.path.dirname(path), exist_ok = True)

    with open(path, 'w+') as f:
      f.write("; {}\n".format(self.__repr__()))

      key_len = max([len(i) for i in self.keys()]) + 5
      s       = "{:<" + str(key_len) + "s} = {}\n"
      for key, val in self.items():
        if not key in ["path", "name"]:
          f.write(s.format(key, val))

    return path
    

  def load(self, path):
    assert os.path.isfile(path), "No file found at path {}".format(path)
    with File(path) as f:
      data = f.advance_to(-1, junk = ["^;", "^\n"], hold_all = True, quiet = True)
      for line in data:
        line = line.strip("\n").split()
        key, val = line[0], " ".join(line[2:])
        self[key] = val

