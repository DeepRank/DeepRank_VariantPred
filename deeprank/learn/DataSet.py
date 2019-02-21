import os
import sys
import time
import h5py
import pickle

from torch import FloatTensor

import numpy as np

from deeprank.generate import NormParam, MinMaxParam, NormalizeData
from deeprank.tools import sparse
from tqdm import tqdm

# import torch.utils.data as data_utils
# The class used to subclass data_utils.Dataset
# but that conflict with Sphinx that couldn't build the API
# It's apparently not necessary though and works without subclassing

class DataSet():

    def __init__(self,database, test_database = None,
                 select_pdb = None,
                 select_feature = 'all', select_target = 'DOCKQ',
                 normalize_features = True, normalize_targets = True,
                 target_ordering=None,
                 dict_filter = None, pair_chain_feature = None,
                 transform_to_2D = False, projection = 0,
                 grid_shape = None,
                 clip_features = True, clip_factor = 1.5,
                 tqdm = False, process = True):

        '''Generates the dataset needed for pytorch.
        This class hanldes the data generated by deeprank.generate to be used in the deep learning
        part of DeepRank. To create an instance you must provide quite a few arguments.
        Example:
        >>> from deeprank.learn import *
        >>> database = '1ak4.hdf5'
        >>> data_set = DataSet(database,
        >>>                    test_database = None,
        >>>                    grid_shape=(30,30,30),
        >>>                    select_feature = {
        >>>                       'AtomicDensities_ind' : 'all',
        >>>                       'Feature_ind' : ['coulomb','vdwaals','charge','pssm']
        >>>                    },
        >>>                    select_target='IRMSD',
        >>>                    normalize_features = True,
        >>>                    normalize_targets=True,
        >>>                    pair_chain_feature=np.add,
        >>>                    dict_filter={'IRMSD':'<4. or >10.'},
        >>>                    process = True)
        Args:
            database (list(str)): names of the hdf5 files used for the training/validation
                Example : ['1AK4.hdf5','1B7W.hdf5',...]
            test_database (list(str)): names of the hdf5 files used for the test
                Example : ['7CEI.hdf5']
            select_pdb (list(str)): names of complexes used for training/validation/test
                Example : ['1AK4', '1AK4_r001', '1AK4_1w', '1AK4_1w_r001']
                Default: None
            select_feature (dict or 'all', optional): Method to select the features used in the learning
                    If 'all', all the mapped features contained in the HDF5 file will be loaded
                    otherwise a dict must be provided.
                    Example : {AtomicDensities : ['CA','CB'], feature_name : 'all'}
                    Default : 'all'
            select_target (str,optional): Specify which targets are required
                Default : 'DOCKQ'
            normalize_features (Bool, optional): control the normalization of features
                Default : True
            normalize_targets (Bool, optional): control the normalization of the targets
                Default : True
            target_ordering (str): 'lower' (the lower the better) or 'higher' (the higher the better)
                By default is not specified (None) and the code tries to identify it. If indentification fails
                'lower' is assumed
            dict_filter (None or dict, optional): Specify if we filter the complexes based on target values
                Example : {'IRMSD' : '<4. or >10'} (select complexes with IRMSD lower than 4 or larger than 10)
                Default : None
            pair_chain_feature (None or callable, optional): method to pair features of chainA and chainB
                Example : np.sum (sum the chainA and chainB features)
            transform_to_2D (bool, optional):  Boolean to use 2d maps instead of full 3d
                Default : False
            projection (int): Projection axis from 3D to 2D:
                Mapping : 0 -> yz, 1 -> xz, 2 -> xy
                Default = 0
            grid_shape (None or tuple(int), optional): shape of the grid in the hdf5 file. Is not necessary
                if the grid points are still present in the HDF5 file.
            clip_features (bool, optional): remove too large values of the grid.
                Can be needed for native complexes where the coulomb feature might be too large
            clip_factor (float, optional): the features are clipped : at +/-mean + clip_factor * std
            tqdm (bool, optional): Print the progress bar
            process (bool, optional): Actually process the data set. Must be set to False when reusing a model for testing
        '''

        # allow for multiple database
        self.database = database
        if not isinstance(database,list):
            self.database = [database]

        # allow for multiple database
        self.test_database = test_database
        if test_database is not None:
            if not isinstance(test_database,list):
                self.test_database = [test_database]

        # pdb selection
        self.select_pdb = select_pdb or []
        if not isinstance(self.select_pdb, list):
            self.select_pdb = [self.select_pdb]

        # features/targets selection
        self.select_feature = select_feature
        self.select_target  = select_target

        # normalization conditions
        self.normalize_features = normalize_features
        self.normalize_targets = normalize_targets

        # clip the data
        self.clip_features = clip_features
        self.clip_factor = clip_factor

        # shape of the data
        self.input_shape = None
        self.data_shape = None
        self.grid_shape = grid_shape

        # the possible pairing of the ind features
        self.pair_chain_feature = pair_chain_feature

        # get the eventual projection
        self.transform = transform_to_2D
        self.proj2D = projection

        # filter the dataset
        self.dict_filter = dict_filter

        #
        self.target_ordering = target_ordering

        # print the progress bar or not
        self.tqdm=tqdm

        # process the data
        if process:
            self.process_dataset()

    def process_dataset(self):
        """Process the data set.
        Done by default. However must be turned off when one want to test a pretrained model. This can be done
        by setting ``process=False`` in the creation of the ``DataSet`` instance.
        """

        print('\n')
        print('='*40)
        print('=\t DeepRank Data Set')
        print('=')
        print('=\t Training data' )
        for f in self.database:
            print('=\t ->',f)
        print('=')
        if self.test_database is not None:
            print('=\t Test data' )
            for f in self.test_database:
                print('=\t ->',f)
        print('=')
        print('='*40,'\n')
        sys.stdout.flush()


        # check if the files are ok
        self.check_hdf5_files()

        # create the indexing system
        # alows to associate each mol to an index
        # and get fname and mol name from the index
        self.create_index_molecules()

        # get the actual feature name
        self.get_feature_name()

        # get the pairing
        self.get_pairing_feature()

        # get grid shape
        self.get_grid_shape()

        # get the input shape
        self.get_input_shape()

        # get the target ordering
        self._get_target_ordering()

        # get renormalization factor
        if self.normalize_features or self.normalize_targets:
            self.get_norm()


        print('\n')
        print("   Data Set Info")
        print('   Training set        : %d conformations' %self.ntrain)
        print('   Test set            : %d conformations' %(self.ntot-self.ntrain))
        print('   Number of channels  : %d' %self.input_shape[0])
        print('   Grid Size           : %d x %d x %d' %(self.data_shape[1],self.data_shape[2],self.data_shape[3]))
        sys.stdout.flush()



    def __len__(self):
        """Get the length of the dataset
        Returns:
            int: number of complexes in the dataset
        """
        return len(self.index_complexes)


    def __getitem__(self,index):
        """Get one item from its unique index.
        Args:
            index (int): index of the complex
        Returns:
            dict: {'mol':[fname,mol],'feature':feature,'target':target}
        """

        debug_time = False
        t0 = time.time()
        fname,mol = self.index_complexes[index]
        feature, target = self.load_one_molecule(fname,mol)

        if self.clip_features:
            feature = self._clip_feature(feature)

        if self.normalize_features:
            feature = self._normalize_feature(feature)

        if self.normalize_targets:
            target = self._normalize_target(target)

        if self.pair_chain_feature:
            feature = self.make_feature_pair(feature,self.pair_indexes,self.pair_chain_feature)

        if self.transform:
            feature = self.convert2d(feature,self.proj2D)

        return {'mol':[fname,mol],'feature':feature,'target':target}


    def check_hdf5_files(self):
        """Check if the data contained in the hdf5 file is ok."""

        print("   Checking dataset Integrity")
        remove_file = []
        for fname in self.database:
            try:
                f = h5py.File(fname,'r')
                mol_names = list(f.keys())
                if len(mol_names) == 0:
                    print('    -> %s is empty ' %fname)
                    remove_file.append(fname)
                f.close()
            except:
                print('    -> %s is corrputed ' %fname)
                remove_file.append(fname)

        for name in remove_file:
            self.database.remove(name)

    def create_index_molecules(self):
        '''Create the indexing of each molecule in the dataset.
        Create the indexing: [ ('1ak4.hdf5,1AK4_100w),...,('1fqj.hdf5,1FGJ_400w)]
        This allows to refer to one complex with its index in the list
        '''
        print("   Processing data set")

        self.index_complexes = []

        desc = '{:25s}'.format('   Train dataset')
        if self.tqdm:
            data_tqdm = tqdm(self.database,desc=desc,file=sys.stdout)
        else:
            print('   Train dataset')
            data_tqdm = self.database
        sys.stdout.flush()

        for fdata in data_tqdm:
            if self.tqdm:
                data_tqdm.set_postfix(mol=os.path.basename(fdata))
            try:
                fh5 = h5py.File(fdata,'r')
                mol_names = list(fh5.keys())
                if self.select_pdb:
                    mol_names = set(self.select_pdb).intersection(mol_names)
                for k in mol_names:
                    if self.filter(fh5[k]):
                        self.index_complexes += [(fdata,k)]
                fh5.close()
            except Exception as inst:
                print('\t\t-->Ignore File : ' + fdata)
                print(inst)

        self.ntrain = len(self.index_complexes)
        self.index_train = list(range(self.ntrain))

        if self.test_database is not None:

            desc = '{:25s}'.format('   Test dataset')
            if self.tqdm:
                data_tqdm = tqdm(self.test_database,desc=desc,file=sys.stdout)
            else:
                data_tqdm = self.test_database
                print('   Test dataset')
            sys.stdout.flush()

            for fdata in data_tqdm:
                if self.tqdm:
                    data_tqdm.set_postfix(mol=os.path.basename(fdata))
                try:
                    fh5 = h5py.File(fdata,'r')
                    mol_names = list(fh5.keys())
                    if self.select_pdb:
                        mol_names = set(self.select_pdb).intersection(mol_names)
                    self.index_complexes += [(fdata,k) for k in mol_names]
                    fh5.close()
                except:
                    print('\t\t-->Ignore File : '+fdata)

        self.ntot = len(self.index_complexes)
        self.index_test = list(range(self.ntrain,self.ntot))


    def filter(self,molgrp):
        '''Filter the molecule according to a dictionary.
        The filter is based on the attribute self.dict_filter
        that must be either of the form: { 'name' : cond } or None
        Args:
            molgrp (str): group name of the molecule in the hdf5 file
        Returns:
            bool: True if we keep the complex False otherwise
        Raises:
            ValueError: If an unsuported condition is provided
        '''
        if self.dict_filter is None:
            return True

        for cond_name,cond_vals in self.dict_filter.items():

            try:
                val = molgrp['targets/'+cond_name].value
            except KeyError:
                print('   :Filter %s not found for mol %s' %(cond_name,mol))

            # if we have a string it's more complicated
            if isinstance(cond_vals,str):

                ops = ['>','<','==']
                new_cond_vals = cond_vals
                for o in ops:
                    new_cond_vals = new_cond_vals.replace(o,'val'+o)
                if not eval(new_cond_vals):
                    return False
            else:
                raise ValueError('Conditions not supported', cond_vals)

        return True

    def get_feature_name(self):

        '''
        Create  the dictionary with actual feature_type : [feature names]
        Add _chainA, _chainB to each feature names if we have individual storage
        create the dict if selec_features == 'all'
        create the dict if selec_features['XXX']  == 'all'
        '''

        # open a h5 file in case we need it
        f5 = h5py.File(self.database[0],'r')
        mol_name = list(f5.keys())[0]
        mapped_data = f5.get(mol_name + '/mapped_features/')
        chain_tags = ['_chainA','_chainB']

        # if we select all the features
        if self.select_feature == "all":

            # redefine dict
            self.select_feature = {}

            # loop over the feat types and add all the feat_names
            for feat_type,feat_names in mapped_data.items():
                self.select_feature[feat_type] = [name for name in feat_names]

        # if a selection was made
        else:

            # we loop over the input dict
            for feat_type,feat_names in self.select_feature.items():

                # if for a given type we need all the feature
                if feat_names == 'all':
                    if feat_type in mapped_data:
                        self.select_feature[feat_type] = list(mapped_data[feat_type].keys())
                    else:
                        self.print_possible_features()
                        raise KeyError('Feature type %s not found')

                # if we have stored the individual
                # chainA chainB data we need to expand the feature list
                # however when we reload a pretrained model we already
                # come with _chainA, _chainB features.
                # So then we shouldn't add the tags
                elif '_ind' in feat_type:
                    self.select_feature[feat_type] = []

                    # loop over all the specified feature names
                    for name in feat_names:

                        # check if there is not _chainA or _chainB in the name
                        cond = [tag not in name for tag in chain_tags]

                        # if there is no chain tag in the name
                        if np.all(cond):

                            # if we have a wild card e.g. PSSM_*
                            # we check the matches and add them
                            if '*' in name:
                                match = name.split('*')[0]
                                possible_names = list(mapped_data[feat_type].keys())
                                match_names = [n for n in possible_names if n.startswith(match)]
                                self.select_feature[feat_type] += match_names

                            # if we don't have a wild card we append
                            # <feature_name>_chainA and <feature_name>_chainB
                            # to the list
                            else:
                                self.select_feature[feat_type] += [name+tag for tag in chain_tags]

                        # if there is a chain tag in the name
                        # (we probably relaod a pretrained model)
                        # and we simply append the feaature name
                        else:
                            self.select_feature[feat_type].append(name)

                else:
                    self.print_possible_features()
                    raise ValueError('Feature selection not recognized')
        f5.close()

    def print_possible_features(self):
        """Print the possible features in the group."""

        f5 = h5py.File(self.database[0],'r')
        mol_name = list(f5.keys())[0]
        mapgrp = f5.get(mol_name + '/mapped_features/')

        print('\nPossible Features:')
        print('-'*20)
        for feat_type in list(mapgrp.keys()):
            print('== %s' %feat_type)
            for fname in list(mapgrp[feat_type].keys()):
                print('   -- %s' %fname)

        if self.select_feature is not None:
            print('\nYour selection was:')
            for feat_type,feat in self.select_feature.items():
                if feat_type not in list(mapgrp.keys()):
                    print('== \x1b[0;37;41m' + feat_type + '\x1b[0m')
                else:
                    print('== %s' %feat_type)
                    if isinstance(feat,str):
                        print('   -- %s' %feat)
                    if isinstance(feat,list):
                        for f in feat:
                            print('  -- %s' %f)

        print("You don't need to specify _chainA _chainB for each feature. The code will append it automatically")

    def get_pairing_feature(self):
        """Creates the index of paired features.
        """

        if self.pair_chain_feature:

            self.pair_indexes = []
            start = 0
            for feat_type,feat_names in self.select_feature.items():
                nfeat = len(feat_names)
                if '_ind' in feat_type:
                    self.pair_indexes += [ [i,i+1] for i in range(start,start+nfeat,2)]
                else:
                    self.pair_indexes += [ [i] for i in range(start,start+nfeat)]
                start += nfeat

    def get_input_shape(self):

        """Get the size of the data and input.
        Reminder :
        self.data_shape  : shape of the raw 3d data set
        self.input_shape : input size of the CNN (potentially after 2d transformation)
        """

        fname = self.database[0]
        feature,_ = self.load_one_molecule(fname)
        self.data_shape = feature.shape

        if self.pair_chain_feature:
            feature = self.make_feature_pair(feature,self.pair_indexes,self.pair_chain_feature)

        if self.transform:
            feature = self.convert2d(feature,self.proj2D)

        self.input_shape = feature.shape


    def get_grid_shape(self):

        '''Get the shape of the matrices.
        Raises:
            ValueError: If no grid shape is provided or is present in the HDF5 file
        '''

        fname = self.database[0]
        fh5 = h5py.File(fname,'r')
        mol = list(fh5.keys())[0]

        # get the mol
        mol_data = fh5.get(mol)

        # get the grid size
        if self.grid_shape is None:

            if 'grid_points' in mol_data:
                nx = mol_data['grid_points']['x'].shape[0]
                ny = mol_data['grid_points']['y'].shape[0]
                nz = mol_data['grid_points']['z'].shape[0]
                self.grid_shape = (nx,ny,nz)

            else:
                raise ValueError('Impossible to determine sparse grid shape.\n Specify argument grid_shape=(x,y,z)')

        fh5.close()

    def get_norm(self):
        """Get the normalization values for the features.
        """

        print("   Normalization factor :")

        # declare the dict of class instance
        # where we'll store the normalization parameter
        self.param_norm = {'features':{},'targets':{}}
        for feat_type,feat_names in self.select_feature.items():
            self.param_norm['features'][feat_type] = {}
            for name in feat_names:
                self.param_norm['features'][feat_type][name] = NormParam()
        self.param_norm['targets'][self.select_target] = MinMaxParam()

        # read the normalization
        self._read_norm()

        # make array for fast access
        self.feature_mean,self.feature_std = [],[]
        for feat_type,feat_names in self.select_feature.items():
            for name in feat_names:
                self.feature_mean.append(self.param_norm['features'][feat_type][name].mean)
                self.feature_std.append(self.param_norm['features'][feat_type][name].std)

        self.target_min = self.param_norm['targets'][self.select_target].min
        self.target_max = self.param_norm['targets'][self.select_target].max

    def _read_norm(self):
        """Read or create the normalization file for the complex.
        """
        # loop through all the filename
        for f5 in self.database:

            # get the precalculated data
            fdata = os.path.splitext(f5)[0]+'_norm.pckl'

            # if the file doesn't exist we create it
            if not os.path.isfile(fdata):
                print("      Computing norm for ", f5)
                norm = NormalizeData(f5,shape=self.grid_shape)
                norm.get()

            # read the data
            data = pickle.load(open(fdata,'rb'))

            # handle the features
            for feat_type,feat_names in self.select_feature.items():
                for name in feat_names:
                    mean = data['features'][feat_type][name].mean
                    var = data['features'][feat_type][name].var
                    if var == 0:
                        print('  : STD is null for %s in %s' %(name,f5))
                    self.param_norm['features'][feat_type][name].add(mean,var)

            # handle the target
            minv = data['targets'][self.select_target].min
            maxv = data['targets'][self.select_target].max
            self.param_norm['targets'][self.select_target].update(minv)
            self.param_norm['targets'][self.select_target].update(maxv)

        # process the std
        nfile = len(self.database)
        for feat_types,feat_dict in self.param_norm['features'].items():
            for feat in feat_dict:
                self.param_norm['features'][feat_types][feat].process(nfile)
                if self.param_norm['features'][feat_types][feat].std == 0:
                    print('  Final STD Null for %s/%s. Changed it to 1' %(feat_types,feat))
                    self.param_norm['features'][feat_types][feat].std = 1

    def _get_target_ordering(self):
        """Determine if ordering of the target.
        This can be lower the better or higher the better
        If it can't determine the ordering 'lower' is assumed
        """

        lower_list = ['IRMSD','LRMSD','HADDOCK']
        higher_list = ['DOCKQ','Fnat']
        NA_list = ['binary_class','BIN_CLASS', 'class']

        if self.select_target in lower_list:
            self.target_ordering = 'lower'
        elif self.select_target in higher_list:
            self.target_ordering = 'higher'
        elif self.select_target in NA_list:
            self.target_ordering = None
        else:
            print('  Target ordering unidentified. lower assumed')
            self.target_ordering = 'lower'

    def backtransform_target(self,data):
        """Returns the values of the target after de-normalization.
        Args:
            data (list(float)): normalized data
        Returns:
            list(float): un-normalized data
        """

        data = FloatTensor(data)
        data *= self.target_max
        data += self.target_min
        return data.numpy()

    def _normalize_target(self,target):
        """Normalize the values of the targets.
        Args:
            target (list(float)): raw data
        Returns:
            list(float): normalized data
        """

        target -= self.target_min
        target /= self.target_max
        return target

    def _normalize_feature(self,feature):
        """Normalize the values of the features.
        Args:
            feature (np.array): raw feature values
        Returns:
            np.array: normalized feature values
        """

        for ic in range(self.data_shape[0]):
            feature[ic] = (feature[ic]-self.feature_mean[ic])/self.feature_std[ic]
        return feature

    def _clip_feature(self,feature):
        """Clip the value of the features at +/- mean + clip_factor * std.
        Args:
            feature (np.array): raw feature values
        Returns:
            np.array: clipped feature values
        """

        w = self.clip_factor
        for ic in range(self.data_shape[0]):
            minv = self.feature_mean[ic] - w*self.feature_std[ic]
            maxv = self.feature_mean[ic] + w*self.feature_std[ic]
            feature[ic] = np.clip(feature[ic],minv,maxv)
            #feature[ic] = self._mad_based_outliers(feature[ic],minv,maxv)
        return feature

    @staticmethod
    def _mad_based_outliers(points, minv, maxv, thresh=3.5):
        """Mean absolute deviation based outlier detection. (Experimental).
        Args:
            points (np.array): raw input data
            minv (float): Minimum (negative) value requested
            maxv (float): Maximum (positive) value requested
            thresh (float, optional): Threshold for data detection
        Returns:
            TYPE: data where outliers were replaced by min/max values
        """

        median = np.median(points)
        diff = np.sqrt((points - median)**2)
        med_abs_deviation = np.median(diff)

        if med_abs_deviation == 0:
            return points

        modified_z_score = 0.6745 * diff / med_abs_deviation
        mask_outliers = modified_z_score > thresh

        mask_max = np.abs(points-maxv) < np.abs(points-minv)
        mask_min = np.abs(points-maxv) > np.abs(points-minv)

        points[mask_max * mask_outliers] = maxv
        points[mask_min * mask_outliers] = minv

        return points

    def load_one_molecule(self,fname,mol=None):
        '''Load the feature/target of a single molecule.
        Args:
            fname (str): hdf5 file name
            mol (None or str, optional): name of the complex in the hdf5
        Returns:
            np.array,float: features, targets
        '''

        outtype = 'float32'
        fh5 = h5py.File(fname,'r')

        if mol is None:
            mol = list(fh5.keys())[0]

        # get the mol
        mol_data = fh5.get(mol)

        # get the features
        feature = []
        for feat_type,feat_names in self.select_feature.items():

            # see if the feature exists
            try:
                feat_dict = mol_data.get('mapped_features/'+feat_type)
            except KeyError:
                print('Feature type %s not found in file %s for molecule %s' %(feat_type,fname,mol))
                print('Possible feature types are : ' + '\n\t'.join(list(mol_data['mapped_features'].keys())))

            # loop through all the desired feat names
            for name in feat_names:

                # extract the group
                try:
                    data = feat_dict[name]
                except KeyError:
                    print('Feature %s not found in file %s for mol %s and feature type %s' %(name,fname,mol,feat_type))
                    print('Possible feature are : ' + '\n\t'.join(list(mol_data['mapped_features/'+feat_type].keys())))


                # check its sparse attribute
                # if true get a FLAN
                # if flase direct import
                if data.attrs['sparse']:
                    mat = sparse.FLANgrid(sparse=True,
                                          index=data['index'].value,
                                          value=data['value'].value,
                                          shape=self.grid_shape).to_dense()
                else:
                    mat = data['value'].value

                # append to the list of features
                feature.append(mat)

        # get the target value
        target = mol_data.get('targets/'+self.select_target).value

        # close
        fh5.close()

        # make sure all the feature have exact same type
        # if they don't  collate_fn in the creation of the minibatch will fail.
        # Note returning torch.FloatTensor makes each epoch twice longer ...
        return np.array(feature).astype(outtype),np.array([target]).astype(outtype)

    @staticmethod
    def convert2d(feature,proj2d):
        '''Convert the 3D volumetric feature to a 2D planar data set.
        proj2d specifies the dimension that we want to consider as channel
        for example for proj2d = 0 the 2D images are in the yz plane and
        the stack along the x dimension is considered as extra channels
        Args:
            feature (np.array): raw features
            proj2d (int): projection
        Returns:
            np.array: projected features
        '''
        nc,nx,ny,nz = feature.shape
        if proj2d==0:
            feature = feature.reshape(-1,1,ny,nz).squeeze()
        elif proj2d==1:
            feature = feature.reshape(-1,nx,1,nz).squeeze()
        elif proj2d==2:
            feature = feature.reshape(-1,nx,ny,1).squeeze()

        return feature

    @staticmethod
    def make_feature_pair(feature,pair_indexes,op):
        """Pair the features of both chains.
        Args:
            feature (np.array): raw features
            pair_indexes (list(int)): Index pairs
            op (callable): function to combine the features
        Returns:
            np.array: combined features
        Raises:
            ValueError: if op is not callable
        """

        if not callable(op):
            raise ValueError('Operation not callable',op)

        outtype = feature.dtype
        new_feat = []
        for ind in pair_indexes:
            if len(ind) == 1:
                new_feat.append(feature[ind,...])
            else:
                new_feat.append(op(feature[ind[0],...],feature[ind[1],...]))

        return np.array(new_feat).astype(outtype)
