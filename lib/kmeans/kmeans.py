from numpy import array, sqrt, zeros, ones, inf,random
from DTW_normal import DTW
import scipy.stats
import dtw
import time

class DistanceError (Exception):
	'''Distance calculation method not supported'''
	pass

class IterationError (Exception):
	'''Iteration count must be bigger than 1'''
	pass

class ClusterError (Exception):
	'''number of cluster can't be bigger than half of the total number of tseries'''
	pass

class InitError (Exception):
	'''general error: I can't initialize the clusters, try changing distance measure or provide other dataset'''
	pass

class Means:
	''' class that manages the algorithm of k-means'''
	def __init__(self, it=None, distance="ddtw", fast=False, radius=20, seed=None, tol=0.0001):
		''' This function gets the inputs which are: nrip:number of times the cycle of clustering must be run (if not defined
		 the algorithm runs until the variants between the old and the new centroids is lower than const tol); the flag met defines
		 the method by which the distance between series is calculated (dtw/ddtw/euclidean/pearson); fast: if True use fast dtw;
		 radius: define the accurancy of fastdtw; seed: parameter for random function; tol: define the precision of the kmedoid alghoritm'''
		if not distance in ["dtw", "ddtw", "euclidean", "pearson"]:
			raise DistanceError("distance %s is not implemented" % distance)

		if (it<1) and (it!=None):
			raise IterationError("it must be bigger than zeros" )
		
		self.pyorc=1
		self.fast=fast
		self.radius=radius
		if distance=="ddtw":
			self.deriv=True
		else:
			self.deriv=False
		if distance=="dtw" or distance=="ddtw":
			self.met=0
		elif distance=="euclidean":
			self.met=1
		elif distance=="pearson":
			self.met=2
		else:
			self.met=0
		self.nrip=it
		self.error=tol
		self.seed=seed		
		self.reinit_maxiter=0

	def compute (self, k, mat):
		''' This function takes: number of trends, k; a matrix, mat, (where each row is a timeseries and each column a point of the time series).
Returns indices of centroids and a list which indicates the cluster each time series fit in.'''
		if self.seed==None:
			random.seed(int(time.time()))
		else:
			random.seed(self.seed)
		self.k = k
		self.mat = mat.astype(float)
		self.mat=self.mat.T
		self.r = self.mat.shape[0]
		self.points = zeros(k)
		self.points-=1		
		self.min = zeros((self.r, 2))
		if (self.k>self.r/2):
			raise ClusterError("WTF, the number of cluster can't be bigger than half of the total number of tseries" )
		self.memvar = inf
		self.__centroids() # calls the function that assigns random centroids	# value of the error that determines the stopping of the algorithm of clustering
		self.__compare()	# calls the function that puts each time series with the most similar centroid
		self.__control()	# calls the function that checks that no empty clusters came out from the random choice
		cont=0		
		old_error = self.__calc_err()
		new_error = old_error*(2.0+self.error)
		if not self.nrip:
			while (abs(new_error/old_error-1.0)>self.error) and (cont<500): # calls the function  thet calculates the error
				self.__newcentroids()	# calls the function that calculates new centroids
				self.__compare()
				cont+=1
				old_error=new_error
				new_error=self.__calc_err()
		else:
			for i in range(self.nrip-1):
				self.__newcentroids()
				self.__compare()
		matpoint=[self.mat[i] for i in self.points]
		self.matpoint=matpoint 	# calls the function that prints the output
		self.min=self.min[:,0]
		self.min+=1
		self.points+=1
		self.points=self.points.astype(int)
		self.min=self.min.astype(int)
		return self.points,self.min

	def __calc_err(self):
		''' It calculates the error which is the difference between the variances of the previous and the current cycle '''
		varianza = zeros (self.k)
		for i in range(self.k):	# cycle that calculates the variance of each centroid
			div=0
			for j in range(self.r):
				if self.min[j,0]==self.points[i]:
					varianza[i]+=self.min[j,1]**2
					div+=1
			varianza[i]=varianza[i]/div
		return	varianza.sum(axis=0)
	

	def __compare(self):
		''' It assignes each series to the nearest centroid '''
		for i in range(self.r):	# cycle that scrolls every time series
			listdiff = zeros(self.k)
			for j in range(self.k):
				listdiff[j] = self.__difference(self.mat[i].copy(), self.mat[self.points[j]].copy())	# records in listdiff the distance between the time series i and the centroid self.points[j]
			for x, val in enumerate(listdiff):
				if val == listdiff.min():
					self.min[i,0] = self.points[x]	# sefl.min is a matrix that contains a line for each time series, in the first it's recorded the centroid from which it is closer and in the second the distance from that centroid
			self.min[i,1] = listdiff.min()
			

	def __centroids(self):
		''' It gives tha array named self.points which contains the index of the lines of mat that contain the selected centroids'''
		for i in range(self.k):
			cond = 0			
			while cond == 0:				# cycle that picks k different numbers randomly
				t = random.randint(self.r)
				if t in self.points:
					cond = 0
				else:
					self.points[i] = t
					cond = 1
					#print i
					#print range(i-1,-1,-1)
					#for j in range(i-1,-1,-1):
						#print "valor j",j
						#if (self.__difference(self.mat[self.points[j]].copy(),self.mat[self.points[i]].copy())==0.):
							#print self.__difference(self.mat[self.points[j]].copy(),self.mat[self.points[i]].copy())
							#print "condizione"
							#cond=0
		
	
	def __difference (self, a, b):
		''' This fuction allows the user to choose between dtw/ddtw, euclidean distance or Pearson correlation when clustering '''
		t=0.0
		if self.met==0:
			t=self.__difference_dtw (a,b)
		elif self.met==1:
			t=self.__difference_eucl (a,b)
		elif self.met==2:
			t=self.__difference_pearson (a,b)
		
		return t

	def __difference_eucl(self, a, b):
		''' It returns the euclidean distance between 2 series '''
		val = 0 
		for i in range(self.mat.shape[1]):
			val += (a[i] - b[i])**2
		return sqrt(val)

	def __difference_dtw(self, a, b):
		''' It returns the distance between 2 series calculated with the dtw algorithm '''
		if self.pyorc==0:
			m=DTW(a, b)
			temp=m.run(self.deriv,0)
		if self.pyorc==1:
			temp=dtw.compute_dtw(a,b,False,self.deriv,self.fast,self.radius)	
		return temp

	def __difference_pearson (self, a, b):
		''' It returns the distance between 2 series computed with the Pearson correlation '''
		t=scipy.stats.pearsonr(a, b)
		return t[1]

	def __newcentroids(self):
		''' It finds a new set of centroids: for each cluster it picks as new centroid the time series which is closest to the average of the distances from the old centroid and the other series in that cluster '''
		for i in range(self.k):
			media = zeros(self.mat.shape[1])
			index = 0
			for j in range(self.r):	# average calculation
				if self.min[j,0] == self.points[i]:
					index+=1
					for k in range(self.mat.shape[1]):
						media[k] += self.mat[j,k]
						
			media /= index
			mini = inf
			for j in range(self.r):		# finds the time series wich has the closest distance to the average of the distances from the centroid to each time series in that cluster
				if self.min[j,0] == self.points[i]:
					dif=self.__difference(self.mat[j].copy(),media.copy())
					if mini>dif:
						mini = dif
						centroi = j
			self.points[i]=centroi
		

	def __control(self):
		''' It checks if there are empty clusters or clusters with only one time series'''
		cond=zeros(self.k)
		while (0 in cond):
			cond=ones(self.k)
			for i in range(self.k): # cycle that records in cond the number of the series 'linked' to each centroid
				cont=0
				for j in range(self.r):
					if self.min[j,0]==self.points[i]:
						cont+=1
				if cont<=1:
					print "EMPTY CLUSTER:RE-INIT"
					self.reinit_maxiter+=1
					if self.reinit_maxiter>10:
						raise InitError("general error: I can't initialize the clusters, try changing distance measure or provide other dataset" )
					self.__centroids() # if empty clusters are found this function reassign centroids and checks again
					self.__compare()
					cond[i]=0
		
				

			

if __name__ == "__main__":				
	k = 2	# number of clusters the time series have to be divided in
	mat = array(   [[4,2,6,1],[4,3,6,6],[1,2,4,4],	# each line is a time series
       		         [7,5,7,4],[8,6,5,2],[7,8,9,1],
        	        [1,2,4,4],[7,5,9,7],[3,1,4,5]] )
	m = Means(k, mat)   
