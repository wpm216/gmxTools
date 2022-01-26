import parmed
import os
import numpy as np
from ..gmx import load_top, load_gro
from fileParser import make_parents, File
from ..objects import mdp as Mdp

# ---------------------------------------------------------------------------- #
# ---------------------------------------------------------------------------- #

def tabulate_in_topology(top_path, d_lists, table_names, k_list = [], path = "", write_multiples = False):
  """ Edits a molecular topology so that the functional forms of the dihedrals
      in d_lists are tabulated with the corresponding table_names.
      Returns a snippet to append to the gmx mdrun command, corresponding to 
      the current paths of the tables.

      WARNING: This will mess up the table numbers for topologies which
                already have some tabuated dihedrals.
  """

  if type(d_lists) is np.ndarray:
    d_lists = [list(i) for i in d_lists]
  
  if not path:
    base, ext = os.path.splitext(top_path)
    path = base + "_tabulated" + ext

  if not k_list:
    k_list = [1.0] * len(d_lists)

  # Make the string of table names
  final_table_names = []
  for i, table in enumerate(table_names):
    ending = "_d{}.xvg".format(i)
    if not table.endswith(ending):
      table += ending

    final_table_names.append(table) # the method returns this as a string.
    
  # Use this as the argument for the -tableb flag in mdrun
  table_str = " ".join(final_table_names)

  with File(top_path) as f, open(path, 'w+') as p:

    while not f.eof:

      # Copy the file over until we hit the dihedrals section.
      f.advance_to(["\[ dihedrals \]", "\[ dihedraltypes \]"], extra = 1, write_to = p, quiet = True)

      # Hold onto the dihedral data so we can analyze it.
      dihedrals_raw = f.advance_to("\[", hold_all = True, junk = ["^\n", "^;"],
                                    exclude = True, quiet = True)

      matched = [] # only tabulate each dihedral once
      for dih in dihedrals_raw:
        d = dih.split()
        d_atoms = [int(i) for i in d[:4]] if isinstance(d_lists[0][0], (int, np.int64)) else d[:4]
        d_type  = d[4]

        fwd_match = any([d_atoms == i for i in d_lists])
        bwd_match = any([d_atoms[::-1] == i for i in d_lists])
        improper  = True if d_type == 4 else False

        write_this_dih = True
        if (fwd_match or bwd_match) and not improper:
          
          if d_atoms in matched and not write_multiples: 
            write_this_dih = False
          else:
            matched.append(d_atoms)
            idx = d_lists.index(d_atoms) if fwd_match else d_lists.index(d_atoms[::-1])

            if path.endswith("top"):
              s   = "{:>7d}{:>7d}{:>7d}{:>7d}{:>6d}{:>7d}{:>10.5f}; tabulated with {}\n"
            else:
              s   = "{:>8s}{:>8s}{:>8s}{:>8s}{:>8d}{:>9d}{:>26.5f}; tabulated with {}\n"

            table = os.path.basename(final_table_names[idx])
            dih = s.format(*d_atoms, 8, idx, k_list[idx], table)

        else:
          dih = dih # leave it untouched

        if write_this_dih:
          p.write(dih)

      # Copy the remainder of the file over.
      p.write("\n")
      f.advance_to(["\[ dihedrals \]", "\[ dihedraltypes \]"], write_to = p, include_first = True, quiet = True)

  return table_str

# ---------------------------------------------------------------------------- #

def zero_dihedrals(topfile, d_lists, path):

  top = load_top(topfile)
  
  if type(d_lists[0]) is int:
    assert len(d_lists) == 4
    d_lists = [d_lists]
  else:
    assert type(d_lists[0]) is list
    assert all(len(d) == 4 for d in d_lists)

  for d in d_lists:
    __zero_dihedral(top, d)

  top.unchange()
  top.write(path)

  return path

# ---------------------------------------------------------------------------- #

def __zero_dihedral(top, d_idxs):

  # Load file and atoms
  assert type(top) is parmed.gromacs.GromacsTopologyFile
  d_list = [top.atoms[int(i)-1] for i in d_idxs]
  d_fwd  = parmed.topologyobjects.Dihedral(*d_list)
  d_rev  = parmed.topologyobjects.Dihedral(*d_list[::-1])

  found_one = False
  for dih in top.dihedrals:
    if any(dih.same_atoms(d) and dih.improper == d.improper for d in [d_fwd, d_rev]):
      dih.type.phi_k = 0
      found_one = True

  if not found_one:
    print("WARNING: Didn't find any dihedral {} in the topology.".format(d_list))

# ---------------------------------------------------------------------------- #

def zero_dihedral(topfile, d_list, path):
  assert type(d_list[0]) is int and len(d_list) == 4
  return zero_dihedrals(topfile, [d_list], path)

# ---------------------------------------------------------------------------- #
# ---------------------------------------------------------------------------- #

def restrain_dihedral(topfile, grofile, d_list, path, force = - 10 ** 7):
  """ Light wrapper around restrain_dihedrals """

  # Validate inputs.
  assert all(type(i) is int for i in d_list) and len(d_list) == 4
  d_lists = [d_list]
  return restrain_dihedrals(topfile, grofile, d_lists, path, force = force)

# ---------------------------------------------------------------------------- #

def restrain_dihedrals(topfile, grofile, d_lists, path, force = -10 ** 7):
  
  """
  Restrain the dihedrals specified by d_lists (list of 4-index lists, origin = 1).
  Uses parmed. Writes a topology file with all dihedral parameters specified explicitly
  for each dihedral. This avoids the potential messes of changing dihedral 
  types in the forcefield and of accidentally adding 1-4 interactions.

  """
    
  # Validate inputs.
  if type(d_lists[0]) is int:
    assert len(d_lists) == 4
    d_lists = [d_lists]
  else:
    assert type(d_lists[0]) is list
    assert all(len(d) == 4 for d in d_lists)

  if not path.endswith(".top"): path += ".top"

  # Load files
  top = load_top(topfile)
  gro = load_gro(grofile)

  # Instantiate restrained dihedrals.
  for d_list in d_lists:
    d, d_type = __add_restraint(top, gro, d_list, force = force)

  make_parents(path)
  top.write(path)

  return path

# ---------------------------------------------------------------------------- #

def __add_restraint(top, gro, d_list, force = -10 ** 7):

  assert force < 0
  assert all(type(i) is int for i in d_list) and len(d_list) == 4

  d_atoms    = [gro.atoms[int(i)-1] for i in d_list]
  d          = parmed.topologyobjects.Dihedral(*d_atoms)
  d_val      = d.measure()
  scee, scnb = top.dihedrals[0].type.scee, top.dihedrals[0].type.scnb # assumed same for all
  d_type     = parmed.topologyobjects.DihedralType(force, 1, d_val, scee, scnb)
  d.type     = d_type

  top.dihedrals.append(d)
  top.dihedral_types.append(d_type)
  top.dihedrals.claim()
  top.dihedral_types.claim()
  
  return d, d_type

# ---------------------------------------------------------------------------- #
# ---------------------------------------------------------------------------- #

def freeze_dihedral(mdpfile, d_list, path = None):
  """ Freezes atoms involved in the dihedral d_list. """

  if path.endswith(".mdp") or path.endswith(".ndx"):
    path = os.path.splitext(path)[0]

  if not path:
    path = os.path.splitext(mdpfile)[0] + "_frozen"
    make_parents(path)

  mdp = Mdp(mdpfile)
  mdp.freezegrps = "dih_frozen"
  mdp.freezedim  = "Y Y Y"

  mdp_frozen = path + ".mdp"
  mdp.write(mdp_frozen)

  ndx_frozen = path + ".ndx"
  with open(ndx_frozen, 'w+') as f:
    f.write("[ dih_frozen ]\n")
    f.write(" {} {} {} {}\n\n".format(*d_list))

  return mdp_frozen, ndx_frozen
 


