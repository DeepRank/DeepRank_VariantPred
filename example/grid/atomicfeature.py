import time
from deeprank.tools import atomicFeature
	
t0 = time.time()
PDB = 'complex.pdb'
FF = './forcefield/'
atfeat = atomicFeature(PDB,
	                   param_charge = FF + 'protein-allhdg5-4_new.top',
					   param_vdw    = FF + 'protein-allhdg5-4_new.param',
					   patch_file   = FF + 'patch.top')

atfeat.assign_parameters()
atfeat.evaluate_pair_interaction()
atfeat.export_data()
atfeat.sqldb.close()
print('Done in %f s' %(time.time()-t0))
