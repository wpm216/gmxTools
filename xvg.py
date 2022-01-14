from utils.fileIO import File
import numpy as np
from sys import exit
import matplotlib.pyplot as plt

class xvg(File):
  
  def __init__(self, fp, mode = 'r'):
    super().__init__(fp, mode)

    # Gather mandatory data
    self.title = self.advance_to("title")[11:]
    x = self.advance_to("xaxis", hold_all = True, tf = lambda x: x[18:].strip("\n").replace('"',''))[0]
    self.labels = [x.split()[0]]
    try:
      self.units = [x.split()[1].replace("(", "").replace(")","")]
      self.units += self.advance_to("yaxis", hold_all = True, tf = self.clean_units)[0]
    except IndexError:
      self.units = None
    self.axtype = self.advance_to("TYPE")[6:]
    self.data = []

    # Gather optional data, halting at onset of data
    self.advance_to(["subtitle", "legend"])[11:]
    self.subtitle = self.cl[11:] if "subtitle" in self.cl else ""
    self.advance_to(["^@ s0", "^ "])
    if self.cl.startswith("@"):
      self.labels += self.advance_to("^ ", hold_all = True, tf = lambda x: x[12:].strip("\n").replace('"',''),
                                        include_first = True, exclude = True)
    else:
      self.labels = None     

    # Gather data
    n_frames = 0
    while self.cl:
      n_frames += 1
      
      # add in extra dimension if needed (or stack)
      self.data.append(np.array(self.advance_to("&", hold_all = True, include_first = True,
                        tf = lambda x: [float(i) for i in x.strip("\n").split()],
                        quiet = True)))

    if n_frames == 1:
      self.data = self.data[0]


  def plot(self, labels = None):
    plt.figure()
    if labels is None:
      if self.units:
        for i, (lab, u) in enumerate(zip(self.labels, self.units)):
          if lab == "Time": continue
          plt.plot(self.data[:, 0], self.data[:, i], label = "{} [{}]".format(lab, u)) 
    else:
      if type(labels) is str: labels = [labels]
      for lab in labels:
        i = self.labels.index(lab) # Will raise ValueError if lab not in self.labels
        plt.plot(self.data[:, 0], self.data[:, i], label = "{} [{}]".format(lab, self.units[i])) 
    plt.xlabel("Time [ps]")
    plt.legend()
    plt.show()
    
  @staticmethod
  def clean_units(u):
    """ cleans up the unit from the xvg file """
    u = u[18:].strip("\n")
    to_remove = ["(", ")", ",", '"']
    for s in to_remove:
      u = u.replace(s, '')
    return u.split()

