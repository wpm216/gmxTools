from utils.gmx.xvg import xvg
from argparse import ArgumentParser as AP

def main(name, labels = None, print_labels = False):
  a = xvg(name)
  if print_labels: print("Labels: {}\nUnits: {}".format(a.labels, a.units))
  if labels:
    a.plot(labels)
  else:
    a.plot()
  return a

if __name__ == "__main__":
  parser = AP("Plot an xvg file with python because xmgrace doesn't work on degennes :(")
  parser.add_argument("-f", "--file_in", required = True)
  parser.add_argument("-l", "--labels", nargs = "+", default = None)
  parser.add_argument("-s", "--show_labels", default = False, action='store_true')
  d = parser.parse_args()
  main(d.file_in, d.labels, d.show_labels)


