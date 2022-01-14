# utilities to help with running gromacs. very sketchy. should implement
#  https://gmxapi.readthedocs.io/en/latest/index.html moving forward.

import subprocess
import os
import stat
import shutil
from utils.fileIO import File, find
from .objects import mdp as Mdp

# ---------------------------------------------------------------------------- #

def _base_cmd():
  if os.path.isfile("/share/software/user/open/gromacs/2018/bin/gmx"):
    return "/share/software/user/open/gromacs/2018/bin/gmx"
  elif os.path.isfile("/home/kjhou/gromacs-install/build/bin/gmx"):
    return "/home/kjhou/gromacs-install/build/bin/gmx"
  else:
    raise ValueError("Couldn't find an executable.")

def _tempfile():
  return "__temp.txt"

def _gromacs_commands():
  """ very incomplete list """
  #TODO: use attributeDict-like language to let gmx.{$command} call gmx.cmd("$command")
  return ["trjcat", "traj"]

class GROMACSInputError(ValueError):
  """ Error found in user input. """
  
  def __init__(self, path, command, error_text, *args):
 
    self.path       = os.path.abspath(path)
    self.command    = command
    self.error_text = error_text
    s               = "\n----\n\nFile:\n{}\n\nCommand:\n{}\nError:\n{}----"
    message         = s.format(self.path, self.command, self.error_text)
    self.message    = message
    super(GROMACSInputError, self).__init__(message)

class GROMACSFatalError(ValueError):
  """ Fatal error """
  
  def __init__(self, path, command, error_text, *args):
 
    self.path       = os.path.abspath(path)
    self.command    = command
    self.error_text = error_text
    s               = "\n----\n\nFile:\n{}\n\nCommand:\n{}\nError:\n{}----"
    message         = s.format(self.path, self.command, self.error_text)
    self.message    = message
    super(GROMACSFatalError, self).__init__(message)


def check_for_error(stderr):
  """ Does a rudimentary check for errors in a GROMACS stderr file. """

  with File(stderr) as f:
    command = f.advance_to("Command line:", extra = 1)

    if f.remaining_has("Error in user input:"):
      f.advance_to("Error in user input:")
      error_text = "".join(f.advance_to("^\n", hold_all = True))
      raise GROMACSInputError(f.abspath, command, error_text)
  
    if f.remaining_has("Fatal error:"):
      f.advance_to("Fatal error:")
      error_text = "".join(f.advance_to("^\n", hold_all = True))
      raise GROMACSFatalError(f.abspath, command, error_text)
  

def check_successful(log):
  """ Checks for the "Finished mdrun on node" line at the end of a logfile. """

  if not os.path.isfile(log):
    return False

  with File(log) as f:
    if log.endswith(".tpr"):  
      pass # grompp file - check for existence
    else: 
      # assume it's an mdrun log file
      f.advance_to("Finished mdrun on", quiet = True)

  if f.eof:
    return False
  else:
    return True


def find_checkpoint(tpr):
  """ Checks for a checkpoint file matching the input tpr file.
      Does this count as an intelligent restart? 
  """
  assert tpr.endswith(".tpr")
  print(tpr)
  cpi = tpr[:-3] + "cpt"
  print(cpi)

  if os.path.isfile(cpi):
    return cpi
  else:
    return None
  

# ---------------------------------------------------------------------------- #

def _run(cmd, args, **kwargs):

  # Create and run command. Get stdout and stderr from kwargs.
  cmd  = cmd.format(*args).split()
  out  = kwargs.get("out", None)
  err  = kwargs.get("err", None)
  pipe = kwargs.get("pipe", None) # e.g. "echo 2" to choose the third option in an interactive gmx command
  log  = kwargs.get("log", None)

  if log and not (out or err):
    out, err = log, log
    kwargs["out"] = log
    kwargs["err"] = log

  if out:
    if os.path.dirname(out):
      os.makedirs(os.path.dirname(out), exist_ok = True)
    f_out = open(out, 'w+')
  else:
    f_out = open(_tempfile(), 'w+')
      
  if err:
    if os.path.dirname(err):
      os.makedirs(os.path.dirname(err), exist_ok = True)
    f_err = open(err, 'w+')
  else:
    f_err = open(_tempfile(), 'w+')

  if pipe:
    ps = subprocess.Popen(pipe.split(), stdout = subprocess.PIPE)
    output = subprocess.check_output(cmd, stdin = ps.stdout, stderr = f_err)
    ps.wait()
  else:
    output = subprocess.run(cmd, stdout = f_out, stderr = f_err)

  f_out.close()
  f_err.close()

  check_for_error(err if err else _tempfile())

  if os.path.isfile(_tempfile()):
    os.remove(_tempfile())
  
  return output

# ---------------------------------------------------------------------------- #

def _add_flags(cmd, args, **kwargs):

  for key, val in kwargs.items():
    if val is not None and key not in ["out", "err", "pipe", "log"]:
      # Being nice about accepting boolean arguments
      if val is False or val == "no":
        cmd += " -{} no".format(key)
      elif val is True or val == "yes":
        cmd += " -{} yes".format(key)
      else:
        cmd += " -{} {{}}".format(_get_key_alias(key))
        args.append(val)
      
  return cmd, args


def _get_key_alias(key):
  """ Some keys need to be aliased to help python digest them. """
  aliases = {"ntry": "try"}
  try:
    return aliases[key]
  except KeyError:
    # No alias needed
    return key

# ---------------------------------------------------------------------------- #

def _gather_outputs(all_outputs, **kwargs):
  return {key: kwargs[key] for key in all_outputs if key in kwargs.keys()}


# ---------------------------------------------------------------------------- #
# ---------------------------------------------------------------------------- #
# ---------------------------------------------------------------------------- #

def grompp(f = None, c = None, p = None, o = "topol.tpr", po = "mdout.mdp", 
           **kwargs):

  assert f and c and p, "missing mandatory inputs (f, c, p)"

  executable = kwargs.get("executable")
  executable = executable if executable else _base_cmd()

  # Parse input arguments.
  cmd = executable + " grompp -f {} -c {} -p {} -o {} -po {}"
  args = [f, c, p, o, po]
  kwargs["f"]  = f
  kwargs["c"]  = c
  kwargs["p"]  = p
  kwargs["o"]  = o
  kwargs["po"] = po

  # Decide first whether to run the file or not.
  overwrite = kwargs.pop("overwrite", False)
  success = check_successful(o)

  # file I/O options
  fio_flags = ["r", "rb", "n", "pp", "t", "e", "imd", "ref"]
  for flag in fio_flags:
    arg = kwargs.get(flag, None)
    if arg:
      cmd += " -{} {{}}".format(flag)
      args.append(arg)

  # Additional arguments
  nice = kwargs.get("nice", None)
  if nice:
    cmd += " -nice {}"
    args.append(nice)

  verbose = kwargs.get("verbose", None)
  if verbose == True or verbose == "yes":
    cmd += " -verbose yes"
  
  time = kwargs.get("time", -1)
  if time != -1:
    cmd += " -time {}"
    args.append(time)

  rmvsbds = kwargs.get("rmvsbds", None)
  if rmvsbds == False or rmvsbds == "no":
    cmd += " -rmvsbds no"

  maxwarn = kwargs.get("maxwarn", 0)
  if maxwarn:
    cmd += " -maxwarn {}"
    args.append(maxwarn)

  zero = kwargs.get("zero", None)
  if zero == True or zero == "yes":
    cmd += " -zero yes"

  renum = kwargs.get("renum", None)
  if renum == False or renum == "no":
    cmd += " -renum no"


  # (possibly) run the preprocessing.
  if not success or overwrite:
    _run(cmd, args, **kwargs) # run it!
  elif success and not overwrite:
    st = "Successful {} found at {}. Skipping simulation and forwarding outputs."
    print(st.format("preprocessing output", o))
  else:
    raise ValueError("Messed the logic up somehow :_D")

  all_outputs = ["po", "pp", "o", "t", "imd", "ref", "out", "err"]
  files       = _gather_outputs(all_outputs, **kwargs)

  return files

# ---------------------------------------------------------------------------- #

def mdrun(s = None, o = "traj.trr", c = "confout.gro", e = "ener.edr", 
          g = "md.log", **kwargs):
  
  assert s and o and c and e and g, "missing mandatory inputs (s)"

  executable = kwargs.pop("executable")
  executable = executable if executable else _base_cmd()

  # Parse input arguments.
  deffnm = kwargs.pop("deffnm", "")
  if deffnm:
    cmd  = executable + " mdrun -s -o -c -e -g -deffnm {}"
    args = [deffnm]
    s    = deffnm + ".tpr"
    o    = deffnm + ".trr"
    c    = deffnm + ".gro"
    e    = deffnm + ".edr"
    g    = deffnm + ".log"
  else:
    cmd  = executable + " mdrun -s {} -o {} -c {} -e {} -g {}"
    args = [s, o, c, e, g]

  # Decide first whether to run the file or not.
  overwrite  = kwargs.pop("overwrite", False)
  success    = check_successful(g)

  # Check if an incomplete run exists (by looking for checkpoint file)
  if (not "cpi" in kwargs.keys() or kwargs["cpi"] is None) and not success:
    checkpoint = find_checkpoint(s)
    if checkpoint:
      st = "Partial checkpoint file found at {}. Restarting simulation from this file."
#       cmd += " -cpi {}".format(checkpoint)
#       args.append(checkpoint)
      kwargs["cpi"] = checkpoint

  # Generate the mdrun command
  cmd, args = _add_flags(cmd, args, **kwargs)

  # (possibly) run the simulation.
  if not success or overwrite:
    _run(cmd, args, **kwargs) # run it!
  elif success and not overwrite:
    st = "Successful {} found at {}. Skipping simulation and forwarding outputs."
    print(st.format("simulation output", o))
  else:
    raise ValueError("Messed the logic up somehow :_D")


  # Gather outputs.
  all_outputs = ["o", "x", "cpo", "c", "e", "g", "dhdl", "field", "tpi", "tpid",
                 "eo", "devout", "runav", "px", "pf", "ro", "ra", "rs", "rt",
                 "mtx", "dn", "if", "swap", "out", "err"]
  if deffnm:
    for key, ext in zip(["o", "c", "e", "g"], [".trr", ".gro", ".edr", ".log"]):
      kwargs[key] = deffnm + ext

  files = _gather_outputs(all_outputs, **kwargs)

  return files

# ---------------------------------------------------------------------------- #

def simulate(name = None, mdp = None, top = None, conf = None, maxwarn = 0, nt = 1,
             ndx = None, po = None, tableb = None, overwrite = False, parent = None,
             cpi = None, restr = None, executable = None, dds = None, pforce=None,
             nb = None):

  """ Light wrapper around grompp and mdrun. """

  assert name and mdp and top and conf
  path = os.path.join(parent, name) if parent else name

  if type(mdp) is Mdp:
    mdp = mdp.write("{}.mdp".format(path))

  po     = "{}_mdout.mdp".format(path) if not po else po
  pplog  = "{}_pp.txt".format(path)
  log    = "{}.txt".format(path)
  tpr    = "{}.tpr".format(path)

  pre = grompp(f = mdp, c = conf, p = top, o = tpr, maxwarn = maxwarn, 
               log = pplog, n = ndx, po = po, overwrite = overwrite, 
               executable = executable, r = restr)

  sim = mdrun(s = tpr, deffnm = path, log = log, nt = nt, tableb = tableb, 
              overwrite = overwrite, cpi = cpi, executable = executable, dds = dds,
              pforce=pforce, nb=nb)

  return pre, sim

# ---------------------------------------------------------------------------- #

def sp(name = None, mdp = None, top = None, conf = None, maxwarn = 0, nt = 1, **kwargs):
  """ Calculates the single point energy of a given configuration. 
      Light wrapper around simulate and cmd. 
      Uses gmx rerun to calculate the sp energy and extracts it from an xvg file.
  """

  assert name and mdp and top and conf

  executable = kwargs.get("executable")
  executable = executable if executable else _base_cmd()

  if type(mdp) is Mdp:
    mdp = mdp.write("{}.mdp".format(name))

  pplog = "{}_pp.txt".format(name)
  log   = "{}.txt".format(name)
  tpr   = "{}.tpr".format(name)
  xvg   = "{}.xvg".format(name)
  elog  = "{}_energy.txt".format(name)

  pre = grompp(f = mdp, c = conf, p = top, o = tpr, maxwarn = maxwarn, log = pplog)
  sim = mdrun(s = tpr, deffnm = name, rerun = conf, log = log, executable = executable, nt = nt)
  res = cmd("energy", f = sim["e"], o = xvg, pipe = 'echo 9', log = elog)

  # Gather results
  with File(xvg) as f:
    f.advance_to("    0.000000 ")
    energy = float(f.cl.split()[-1])

  return energy

# ---------------------------------------------------------------------------- #

def normal_modes(name = None, mdp = None, top = None, conf = None, maxwarn = 0, nt = 1):
  """ Energy minimization. Will 
      Light wrapper around simulate and cmd. 
      Uses gmx rerun to calculate the sp energy and extracts it from an xvg file.
  """

  assert name and mdp and top and conf

  if type(mdp) is Mdp:
    mdp = mdp.write("{}.mdp".format(name))

  pplog = "{}_pp.txt".format(name)
  log   = "{}.txt".format(name)
  tpr   = "{}.tpr".format(name)
  xvg   = "{}.xvg".format(name)
  elog  = "{}_energy.txt".format(name)

  pre = grompp(f = mdp, c = conf, p = top, o = tpr, maxwarn = maxwarn, log = pplog)
  sim = mdrun(s = tpr, deffnm = name, rerun = conf, log = log, nt = nt)
  res = cmd("energy", f = sim["e"], o = xvg, pipe = 'echo 9', log = elog)

  # Gather results
  with File(xvg) as f:
    f.advance_to("    0.000000 ")
    energy = float(f.cl.split()[-1])

  return energy

# ---------------------------------------------------------------------------- #

def cmd(name, **kwargs):

  # Light wrapper around subprocess.run. out and err kwargs are stdout and stderr.
  cmd  = _base_cmd() + " {}".format(name)
  args = []

  cmd, args = _add_flags(cmd, args, **kwargs)
  _run(cmd, args, **kwargs)
  return kwargs

# ---------------------------------------------------------------------------- #
# ---------------------------------------------------------------------------- #
# ---------------------------------------------------------------------------- #

def gro_trajectory(gro_list, outfile):
  """ Since trjcat doesn't work for .gro files, this will concatenate a list
      of gro files into one big gro file. very rudimentary.
  """
      
  os.makedirs(os.path.dirname(outfile), exist_ok = True)
  with open(outfile, 'w+') as f:
    for gro in gro_list:

      if not os.path.isfile(gro):
        raise ValueError("{} is not a valid path.".format(gro))
      
      with open(gro) as g:
        shutil.copyfileobj(g, f)

  return outfile
    
# ---------------------------------------------------------------------------- #
# ---------------------------------------------------------------------------- #

def load_top(topfile):
  import parmed
  top = parmed.gromacs.GromacsTopologyFile(topfile)
  return top

# ---------------------------------------------------------------------------- #

def load_gro(grofile):

  if not grofile.endswith("gro"):

    gro_base = os.path.splitext(grofile)[0]
    dirname  = os.path.dirname(grofile) 

    if grofile.endswith(".log"):
      # assume it's a gaussian logfile.
      from gaussian.logfile import Logfile
      log = Logfile(grofile)
      log.write_gro(os.path.join(dirname, gro_base + ".gro"))
      tempfile = gro_base + ".gro"

    else:
      # assume it's gromacs compatible.
      log      = os.path.join(dirname, "editconf.log")
      cmd("editconf", f = grofile, o = gro_base + ".gro", out = log, err = log)
      tempfile = gro_base + ".gro"

    import parmed
    gro = parmed.gromacs.GromacsGroFile.parse(tempfile)
    os.remove(tempfile)

  else:
    import parmed
    gro = parmed.gromacs.GromacsGroFile.parse(grofile)

  return gro


# ---------------------------------------------------------------------------- #

def load_mdp_list(path):
  """ reads a file that contains a relative or absolute path to an mdp
      file on each line. preserves the file's ordering.
  """

  def find_file(parent, filepath):
    filepath = filepath.strip("\n").strip(" ")
    fp = os.path.join(parent, filepath)
    if os.path.isfile(filepath):
      return filepath
    elif os.path.isfile(fp):
      return fp
    else:
      if os.path.isdir(fp):
        raise ValueError("Directory found at {}, not a file.".format(filepath))
      else:
        raise ValueError("mdp file at path {} not found.".format(filepath))

  get = lambda x: find_file(os.path.dirname(path), x)

  with File(path) as f:
    mdps = f.advance_to(-1, hold_all = True, tf = get, quiet = True, junk = ["^ ", "^\n"])

  return [Mdp(m) for m in mdps]
    




