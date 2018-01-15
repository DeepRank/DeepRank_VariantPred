
#!/usr/bin/env python

from datetime import datetime
import sys
import os
import time
import h5py
import matplotlib.pyplot as plt
import numpy as np

#import torch
import torch
from torch.autograd import Variable
import torch.nn as nn
import torch.nn.functional as F
import torch.optim as optim
import torch.utils.data as data_utils

import torch.cuda

from deeprank.learn import DataSet

class NeuralNet:

	'''
	Train a Convolutional Neural Network for DeepRank

	ARGUMENTS

	data_set
		
		Data set generated by the DeepRankDataSet
		data_set = DeepRankDataSet( ... )

	model

		definition of the NN to use. Must subclass nn.Module.
		See examples in model2D.py and model3d.py

	model_type : '2d' or '3d'

		Specify if we consider a 3D or a 2D convnet 
		This ust matches the model used in the training
		if we specif a 2d CNN the data set is automatically covnerted
		to the correct format.

	proj2d : 0,1 or 2

		specify wich axis is conisdered as a channels during the conversion from
		3d to 2d data type.
		0 -> x-axis is a channel i.e the images are in the yz plane
		1 -> y-axis is a channel i.e the images are in the xz plane
		1 -> z-axis is a channel i.e the images are in the xy plane
	
	task : 'ref' or 'class'

		Task to perform either
		'reg'   for regression 
		'class' for classification
		The loss function, the format of the targets and plot functions
		will be autmatically adjusted dependinf on the task

	plot : True/False

		So fat only a scatter plots of the outputs VS targets
		for training and validatiion set is exported.

	outdir

		output directory where all the files will be written

	USAGE 

		net = NeuralNet( ... )
		(optional) net.optimiser = optim.Adam( ... )
		(optional) net.criterion = nn.CrossEntropy( .... )
		net.train( nepoch=50 )

	'''

	def __init__(self,data_set,model,
				 model_type='3d',proj2d=0,task='reg',
				 cuda=False,ngpu=0,
		         plot=True,outdir='./'):



		#data set and model
		self.data_set = data_set

		# convert the data to 2d if necessary
		if model_type == '2d':
			data_set.convert_dataset_to2d(proj2d=proj2d)

		# task to accomplish 
		self.task = task

		# CUDA required
		self.cuda = cuda
		self.ngpu = ngpu

		# handles GPU/CUDA
		if self.ngpu > 0:
			self.cuda = True

		if self.ngpu == 0 and self.cuda :
			self.ngpu = 1

		# plot or not plot
		self.plot = plot

		# import matplotlib only if we 
		if self.plot:
			import matplotlib.pyplot as plt


		# Set the loss functiom
		if self.task=='reg':
			self.criterion = nn.MSELoss()
			self._plot_scatter = self._plot_scatter_reg

		elif self.task=='class':
			self.criterion = nn.CrossEntropyLoss()
			self._plot_scatter = self._plot_boxplot_class

		else:
			print("Task " + self.task +"not recognized.\nOptions are \n\t 'reg': regression \n\t 'class': classifiation\n\n")
			sys.exit()

		# containers for the losses
		self.losses={'train': [],'valid': [], 'test':[]}

		# output directory
		self.outdir = outdir
		if self.plot:
			if not os.path.isdir(self.outdir):
				os.mkdir(outdir)

		print('\n')
		print('='*40)
		print('=\t Convolution Neural Network')
		print('=\t model     : %s' %model_type)
		print('=\t CNN       : %s' %model.__name__)
		if self.data_set.select_feature == 'all':
			print('=\t features  : all')
		else:
			print('=\t features  : %s' %" / ".join([key for key,_ in self.data_set.select_feature.items()]))
		print('=\t targets   : %s' %self.data_set.select_target)
		print('=\t CUDA      : %s' %str(self.cuda))
		if self.cuda:
			print('=\t nGPU      : %d' %self.ngpu)
		print('='*40,'\n')	


		# check if CUDA works
		if self.cuda and not torch.cuda.is_available():
			print(' --> CUDA not deteceted : Make sure that CUDA is installed and that you are running on GPUs')
			print(' --> To turn CUDA of set cuda=False in DeepRankConvNet')
			print(' --> Aborting the experiment \n\n')
			sys.exit()


		# load the model
		self.net = model(data_set.input_shape)

		#multi-gpu
		if self.ngpu>1:
			ids = [i for i in range(self.ngpu)]
			self.net = nn.DataParallel(self.net,device_ids=ids).cuda()

		# cuda compatible
		elif self.cuda:
			self.net = self.net.cuda()

		# set the optimizer
		self.optimizer = optim.SGD(self.net.parameters(),lr=0.005,momentum=0.9,weight_decay=0.001)

	def train(self,nepoch=50, divide_set=[0.8,0.2], hdf5='data.hdf5',train_batch_size = 10, 
		      preshuffle = True,export_intermediate=True,debug=False):

		'''
		Perform a simple training of the model. The data set is divided in training/validation sets

		ARGUMENTS

		nepoch : Int. number of iterations to go through the training 

		divide_set : the percentage assign to the training, validation and test set.

		train_batch_size : the mini batch size for the training
		
		preshuffle. Boolean Shuffle the data set before dividing it.

		plot_intermediate : plot scatter plots during the training

		'''

		# multi-gpu 
		if self.ngpu > 1:
			train_batch_size *= self.ngpu

		print('\n: Batch Size : %d' %train_batch_size)
		if self.cuda:
			print(': NGPU       : %d' %self.ngpu)

		# hdf5 supprt			
		fname =self.outdir+'/'+hdf5
		if os.path.isfile(fname):
			fname = os.path.splitext(fname)[0] + '_new.hdf5'
		self.f5 = h5py.File(fname,'w')
		

		# divide the set in train+ valid and test
		index_train,index_valid,index_test = self._divide_dataset(divide_set,preshuffle)

		# train the model
		self._train(index_train,index_valid,index_test,
			        nepoch=nepoch,
			        train_batch_size=train_batch_size,
			        export_intermediate=export_intermediate,
			        debug=debug)

		self.f5.close()

	def save_model(self,filename='model.pth.tar'):
		'''
		save the model to disk
		'''
		filename = self.outdir + '/' + filename
		state = {'state_dict'   : self.net.state_dict(),
				'optimizer'    : self.optimizer.state_dict()}
		torch.save(state,filename)

	def load_model(self,filename):
		'''
		load model
		'''
		state = torch.load(filename)
		self.net.load_state_dict(state['state_dict'])
		self.optimizer.load_state_dict(state['optimizer'])

		
	def _divide_dataset(self,divide_set, preshuffle):

		'''
		Divide the data set in atraining validation and test
		according to the percentage in divide_set
		Retun the indexes of  each set
		'''

		# get the indexes of the train/validation set
		ind = np.arange(self.data_set.__len__())
		ntot = len(ind)

		if self.data_set.test_database is None:

			print('No test data base found')
			print('Dividing the train dataset in:')
			print('  : 0.8 -> train')
			print('  : 0.1 -> valid')
			print('  : 0.1 -> test')

			divide_set = [0.8,0.1,0.1]

			if preshuffle:
				np.random.shuffle(ind)

			# size of the subset
			ntrain = int( float(ntot)*divide_set[0] )	
			nvalid = int( float(ntot)*divide_set[1] )
			ntest =  int( float(ntot)*divide_set[2] )
			

			# indexes
			index_train = ind[:ntrain]
			index_valid = ind[ntrain:ntrain+nvalid]
			index_test = ind[ntrain+nvalid:]

		else:

			if preshuffle:
				np.random.shuffle(ind[:self.data_set.ntrain])

			# size of the subset for training
			ntrain = int( float(self.data_set.ntrain)*divide_set[0] )	
			
			# indexes
			index_train = ind[:ntrain]
			index_valid = ind[ntrain:self.data_set.ntrain]
			index_test = ind[self.data_set.ntrain:]

		return index_train,index_valid,index_test



	def _train(self,index_train,index_valid,index_test,
		       nepoch = 50,train_batch_size = 5,
		       tensorboard_writer = None,
		       export_intermediate=False,debug=False):

		'''
		Train the model 
	
		Arguments
		
		index_train : the indexes of the training set
		index_valid : the indexes of the validation set
		nepoch : number of epochs to be performed
		train_batch_size : the mini batch size for the training
		tensorboard_write : the writer for tensor board
		plot_intermediate : plot itnermediate
		debug : if TRUE the data set are statically created
		'''

		# printing options
		nprint = int(nepoch/10)

		# store the length of the training set
		ntrain = len(index_train)

		# pin memory for cuda
		pin = False
		if self.cuda:
			pin = True


		# create the sampler
		train_sampler = data_utils.sampler.SubsetRandomSampler(index_train)
		valid_sampler = data_utils.sampler.SubsetRandomSampler(index_valid)
		test_sampler = data_utils.sampler.SubsetRandomSampler(index_test)

		#  create the loaders
		train_loader = data_utils.DataLoader(self.data_set,batch_size=train_batch_size,sampler=train_sampler,pin_memory=pin)
		valid_loader = data_utils.DataLoader(self.data_set,batch_size=1,sampler=valid_sampler,pin_memory=pin)
		test_loader = data_utils.DataLoader(self.data_set,batch_size=1,sampler=test_sampler,pin_memory=pin)

		# training loop
		av_time = 0.0
		self.data = {}
		for epoch in range(nepoch):

			print('\n: epoch %03d / %03d ' %(epoch,nepoch) + '-'*45)
			t0 = time.time()

			# train the model
			self.train_loss,self.data['train'] = self._epoch(train_loader,train_model=True)
			self.losses['train'].append(self.train_loss)

			# validate the model
			self.valid_loss,self.data['valid'] = self._epoch(valid_loader,train_model=False)
			self.losses['valid'].append(self.valid_loss)

			# test the model
			test_loss,self.data['test'] = self._epoch(test_loader,train_model=False)
			self.losses['test'].append(test_loss)

			# talk a bit about losse
			print('  train loss       : %1.3e\n  valid loss       : %1.3e' %(self.train_loss, self.valid_loss))
			if index_test is not None:
				print('  test loss        : %1.3e' %(test_loss))

			# timer
			elapsed = time.time()-t0
			print('  epoch done in    :', time.strftime('%H:%M:%S', time.gmtime(elapsed)) )

			# remaining time
			av_time += elapsed
			nremain = nepoch-(epoch+1)
			remaining_time = av_time/(epoch+1)*nremain
			print('  remaining time   :',  time.strftime('%H:%M:%S', time.gmtime(remaining_time)))		

			# plot the scatter plots
			if (export_intermediate and epoch%nprint == nprint-1) or epoch==0 or epoch==nepoch-1:
				if self.plot:
					figname = self.outdir+"/prediction_%03d.png" %epoch
					self._plot_scatter(figname)
				self._export_epoch_hdf5(epoch,self.data)


		# plot the losses
		self._export_losses(self.outdir+'/'+'losses.png')

		return torch.cat([param.data.view(-1) for param in self.net.parameters()],0)

	def _epoch(self,data_loader,train_model=True):

		'''
		Perform one single epoch iteration over a data loader
		The option train is True or False and controls
		if the model should be trained or not on the data
		The loss of the model is returned
		'''

		running_loss = 0
		data = {'outputs':[],'targets':[]}

		for (inputs,targets) in data_loader:

			# get the data
			inputs,targets = self._get_variables(inputs,targets)

			# zero gradient
			if train_model:
				self.optimizer.zero_grad()

			# forward + loss
			outputs = self.net(inputs)
			loss = self.criterion(outputs,targets)
			running_loss += loss.data[0]

			# backward + step
			if train_model:
				loss.backward()
				self.optimizer.step()

			# get the outputs for export
			if self.cuda:
				data['outputs'] +=  outputs.data.cpu().numpy().tolist()
				data['targets'] += targets.data.cpu().numpy().tolist()
			else:
				data['outputs'] +=  outputs.data.numpy().tolist()				
				data['targets'] += targets.data.numpy().tolist()

		# transform the output back
		data['outputs']  = self.data_set.backtransform_target(np.array(data['outputs']).flatten())
		data['targets']  = self.data_set.backtransform_target(np.array(data['targets']).flatten())

		return running_loss, data


	def _get_variables(self,inputs,targets):

		'''
		Convert the inout/target in Variables
		the format is different for regression where the targets are float
		and classification where they are int.
		'''

		# if cuda is available
		if self.cuda:
			inputs = inputs.cuda(async=True)
			targets = targets.cuda(async=True)


		# get the varialbe as float by default
		inputs,targets = Variable(inputs),Variable(targets).float()

		# change the targets to long for classification
		if self.task == 'class':
			targets =  targets.long()

		return inputs,targets


	def _export_losses(self,figname):

		'''
		plot the losses vs the epoch
		'''

		print('\n --> Loss Plot')

		color_plot = ['red','blue','green']
		labels = ['Train','Valid','Test']

		fig,ax = plt.subplots()	
		plt.plot(np.array(self.losses['train']),c=color_plot[0],label=labels[0])
		plt.plot(np.array(self.losses['valid']),c=color_plot[1],label=labels[1])
		plt.plot(np.array(self.losses['test']),c=color_plot[2],label=labels[2])

		legend = ax.legend(loc='upper left')
		ax.set_xlabel('Epoch')
		ax.set_ylabel('Losses')

		fig.savefig(figname)
		plt.close()

		for k,v in self.losses.items():
			self.f5.create_dataset('/losses/'+k,data=v)

	def _plot_scatter_reg(self,figname,loaders=None,indexes=None):

		'''
		Plot a scatter plots of predictions VS targets useful '
		to visualize the performance of the training algorithm 
		
		We can plot either from the loaders or from the indexes of the subset
		
		loaders should be either None or a list of loaders of maxsize 3
		loaders = [train_loader,valid_loader,test_loader]

		indexes should be a list of indexes list of maxsize 3
		indexes = [index_train,index_valid,index_test]
		'''

		# abort if we don't want to plot
		if self.plot == False:
			return


		print('\n --> Scatter Plot : ', figname, '\n')
		
		color_plot = {'train':'red','valid':'blue','test':'green'}
		labels = ['train','valid','test']

		fig,ax = plt.subplots()	

		xvalues = np.array([])
		yvalues = np.array([])

		for l in labels:

			targ = self.data[l]['targets']
			out = self.data[l]['outputs']

			xvalues = np.append(xvalues,targ)
			yvalues = np.append(yvalues,out)

			ax.scatter(targ,out,c = color_plot[l],label=l)	
		
		legend = ax.legend(loc='upper left')
		ax.set_xlabel('Targets')
		ax.set_ylabel('Predictions')

		values = np.append(xvalues,yvalues)
		border = 0.1 * (values.max()-values.min())
		ax.plot([values.min()-border,values.max()+border],[values.min()-border,values.max()+border])

		fig.savefig(figname)
		plt.close()


	def _export_epoch_hdf5(self,epoch,data):

		grp_name = 'epoch_%04d' %epoch
		grp = self.f5.create_group(grp_name)
		for k,v in data.items():
			sg = grp.create_group(k)
			for kk,vv in v.items():
				sg.create_dataset(kk,data=vv)


	






