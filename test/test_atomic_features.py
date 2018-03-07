from deeprank.features import AtomicFeature
import numpy as np
import pkg_resources
import unittest

class TestAtomicFeature(unittest.TestCase):
    """Test StructureSimialrity."""

    @staticmethod
    def test_atomic():

        # in case you change the ref don't forget to:
        # - comment the first line (E0=1)
        # - uncomment the last two lines (Total = ...)
        # - use the corresponding PDB file to test
        REF = './1AK4/atomic_features/ref_1AK4_100w.dat'
        pdb = './1AK4/atomic_features/1AK4_100w.pdb'
        test_name = './1AK4/atomic_features/test_1AK4_100w.dat'

        # get the force field included in deeprank
        # if another FF has been used to compute the ref
        # change also this path to the correct one
        FF = pkg_resources.resource_filename('deeprank.features','') + '/forcefield/'

        # declare the feature calculator instance
        atfeat = AtomicFeature(pdb,
                               param_charge = FF + 'protein-allhdg5-4_new.top',
                               param_vdw    = FF + 'protein-allhdg5-4_new.param',
                               patch_file   = FF + 'patch.top')
        # assign parameters
        atfeat.assign_parameters()

        # only compute the pair interactions here
        atfeat.evaluate_pair_interaction(save_interactions=test_name)

        # close the db
        atfeat.sqldb.close()

        # read the files
        f = open(REF)
        ref = f.readlines()
        ref = [r for r in ref if not r.startswith('#') and not r.startswith('Total') and len(r.split())>0]
        f.close()

        f=open(REF)
        ref_tot = f.readlines()
        ref_tot = [r for r in ref_tot if r.startswith('Total')]
        f.close()

        # read the test
        f=open(test_name)
        test = f.readlines()
        test = [t for t in test if len(t.split())>0 and not t.startswith('Total')]
        f.close()

        f=open(test_name)
        test_tot = f.readlines()
        test_tot = [t for t in test_tot if t.startswith('Total')]
        f.close()

        # compare files
        nint = 0
        delta_dist, delta_elec = 0., 0.
        for ltest,lref in zip(test,ref):
            ltest = ltest.split()
            lref = lref.split()


            at_test = ( (ltest[0],ltest[1],ltest[2],ltest[3]),(ltest[4],ltest[5],ltest[6],ltest[7]) )
            at_ref  = ( (lref[1] ,lref[0] ,lref[2] ,lref[3]) ,(lref[5] ,lref[4] ,lref[6] ,lref[7]) )
            if not at_test == at_ref:
                raise AssertionError()

            dtest = np.array(float(ltest[8]))
            dref  = np.array(float(lref[8]))
            delta_dist = np.max([delta_dist,np.abs(dtest-dref)])
            if not np.allclose(dtest,dref,rtol = 1E-3,atol=1E-3):
                raise AssertionError()

            val_test = np.array(ltest[9:11]).astype('float64')
            val_ref  = np.array(lref[9:11]).astype('float64')

            delta_elec = np.min([delta_elec,np.abs(val_ref[0]-val_test[0])])
            delta_vdw = np.min([delta_elec,np.abs(val_ref[1]-val_test[1])])
            if not np.allclose(val_ref,val_test,atol=1E-6):
                raise AssertionError()

            nint += 1

        Etest= np.array([float(test_tot[0].split()[3]),float(test_tot[1].split()[3])])
        Eref = np.array([float(ref_tot[0].split()[3]),float(ref_tot[1].split()[3])])
        if not np.allclose(Etest,Eref):
            raise AssertionError()

if __name__ == '__main__':
    unittest.main()

