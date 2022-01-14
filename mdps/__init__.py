# Loads templates of mdp files. Uses probably the jankiest factory
#  setup in existence.

from utils.gmx.objects import mdp
from utils.fileIO import find
import os

template_path = os.path.join(os.path.dirname(__file__), "templates")


def em():
  return mdp(find(os.path.join(template_path, "em.mdp")))
  
def nvt():
  return mdp(find(os.path.join(template_path, "nvt.mdp")))
  
def npt():
  return mdp(find(os.path.join(template_path, "npt.mdp")))

