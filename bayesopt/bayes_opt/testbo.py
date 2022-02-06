from __future__ import print_function
from __future__ import division

import time
import pickle
import numpy as np
import seaborn as sns
from .gprmy import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import Matern
from .helpers import UtilityFunction, unique_rows, PrintLog, acq_max
from pyDOE import lhs

import matplotlib.pyplot as plt
#from mpl_toolkits.mplot3d import Axes3D



##import math
#import sys
#sys.path.append('deepGP/')
#import AEPDGP_net

class BayesianOptimization(object):

    def __init__(self, f, pbounds, vae=0,verbose=0):
        """
        :param f:
            Function to be maximized.

        :param pbounds:
            Dictionary with parameters names as keys and a tuple with minimum
            and maximum values.

        :param verbose:
            Whether or not to print progress.

        """

        # Store the original dictionarys
        self.pbounds = pbounds
#        print(pbounds)
        self.vae=vae
        # Get the name of the parameters
        self.keys = list(pbounds.keys())

        # Find number of parameters
        self.dim = len(pbounds)

        # Create an array with parameters bounds
        self.bounds = []
        for key in self.pbounds.keys():
            self.bounds.append(self.pbounds[key])
        self.bounds = np.asarray(self.bounds)
#         print(self.bounds)

        # Some function to be optimized
        self.f = f

        # Initialization flag
        self.initialized = False

        # Initialization lists --- stores starting points before process begins
        self.init_points = []
        self.x_init = []
        self.y_init = []

        # Numpy array place holders
        self.X = None
        self.Y = None

        # Counter of iterations
        self.i = 0

        # Internal GP regressor

        self.gp = GaussianProcessRegressor(
            kernel=Matern(length_scale=0.5*np.ones((self.dim)), nu=2.5),
            n_restarts_optimizer=5, hyp_opt_max_iter=1
        )


        # Utility Function placeholder
        self.util = None

        # PrintLog object
        self.plog = PrintLog(self.keys)

        # Output dictionary
        self.res = {}
        # Output dictionary
        self.res['max'] = {'max_val': None,
                           'max_params': None}
        self.res['all'] = {'values': [], 'params': []}

        # Verbose
        self.verbose = verbose
        

    def init(self,init_points,z_m,z_v,ei='ei',xi=1):
        """
        Initialization method to kick start the optimization process. It is a
        combination of points passed by the user, and randomly sampled ones.

        :param init_points:
            Number of random points to probe.
        """

#        # Generate random uniform points
#        l = [np.random.uniform(x[0], x[1], size=init_points)
#             for x in self.bounds]
#        
#        # Concatenate new random points to possible existing
#        # points from self.explore method.
#        self.init_points += list(map(list, zip(*l)))
#        print('initial step')
        np.random.seed(123)
        

#        if (ei=='ei'):
#            #Generate latin hypercube samples
#            print('lhs')
#        boundL = np.min( [tup[0] for tup in self.pbounds.values()])
#        boundU = np.max( [tup[1] for tup in self.pbounds.values()])
#        l = lhs(self.dim,init_points)
#        l = boundL + (boundU-boundL)*l
#        else:
            
        # Generate initial samples from the VAE latent prior
        l = np.random.multivariate_normal(np.zeros(self.dim), 1.0/10*np.diag(np.ones(self.dim)),init_points)

        # Concatenate new random points to possible existing
        # points from self.explore method.
        self.init_points += l.tolist()

        # Create empty list to store the new values of the function
        y_init = []

        # Evaluate target function at all initialization
        # points (random + explore)
        for x in self.init_points:
            y_init.append(self.f(x,self.vae))

            if self.verbose:
                self.plog.print_step(x, y_init[-1])

        # Append any other points passed by the self.initialize method (these
        # also have a corresponding target value passed by the user).
        self.init_points += self.x_init
#         print(self.init_points)

        # Append the target value of self.initialize method.s
        y_init += self.y_init

        # Turn it into np array and store.
        self.X = np.asarray(self.init_points)
        self.Y = np.asarray(y_init)

        # Updates the flag
        self.initialized = True

    def explore(self, points_dict):
        """Method to explore user defined points

        :param points_dict:
        """

        # Consistency check
        param_tup_lens = []

        for key in self.keys:
            param_tup_lens.append(len(list(points_dict[key])))

        if all([e == param_tup_lens[0] for e in param_tup_lens]):
            pass
        else:
            raise ValueError('The same number of initialization points '
                             'must be entered for every parameter.')

        # Turn into list of lists
        all_points = []
        for key in self.keys:
            all_points.append(points_dict[key])

        # Take transpose of list
        self.init_points = list(map(list, zip(*all_points)))

    def initialize(self, points_dict):
        """
        Method to introduce points for which the target function value is known

        :param points_dict:
            dictionary with self.keys and 'target' as keys, and list of
            corresponding values as values.

        ex:
            {
                'target': [-1166.19102, -1142.71370, -1138.68293],
                'alpha': [7.0034, 6.6186, 6.0798],
                'colsample_bytree': [0.6849, 0.7314, 0.9540],
                'gamma': [8.3673, 3.5455, 2.3281],
            }

        :return:
        """

        self.y_init.extend(points_dict['target'])
        for i in range(len(points_dict['target'])):
            all_points = []
            for key in self.keys:
                all_points.append(points_dict[key][i])
            self.x_init.append(all_points)

    def initialize_df(self, points_df):
        """
        Method to introduce point for which the target function
        value is known from pandas dataframe file

        :param points_df:
            pandas dataframe with columns (target, {list of columns matching
            self.keys})

        ex:
              target        alpha      colsample_bytree        gamma
        -1166.19102       7.0034                0.6849       8.3673
        -1142.71370       6.6186                0.7314       3.5455
        -1138.68293       6.0798                0.9540       2.3281
        -1146.65974       2.4566                0.9290       0.3456
        -1160.32854       1.9821                0.5298       8.7863

        :return:
        """

        for i in points_df.index:
            self.y_init.append(points_df.loc[i, 'target'])

            all_points = []
            for key in self.keys:
                all_points.append(points_df.loc[i, key])

            self.x_init.append(all_points)

    def set_bounds(self, new_bounds):
        """
        A method that allows changing the lower and upper searching bounds

        :param new_bounds:
            A dictionary with the parameter name and its new bounds

        """

        # Update the internal object stored dict
        self.pbounds.update(new_bounds)

        # Loop through the all bounds and reset the min-max bound matrix
        for row, key in enumerate(self.pbounds.keys()):

            # Reset all entries, even if the same.
            self.bounds[row] = self.pbounds[key]

    def maximize(self,
                 init_points=5,
                 n_iter=25,
                 acq='ei',
                 kappa=2.576,
                 z_a=1,
                 z_m=0,
                 z_v=1,
                 xi=0.0,
                 **gp_params):
        """
        Main optimization method.

        Parameters
        ----------
        :param init_points:
            Number of randomly chosen points to sample the
            target function before fitting the gp.

        :param n_iter:
            Total number of times the process is to repeated. Note that
            currently this methods does not have stopping criteria (due to a
            number of reasons), therefore the total number of points to be
            sampled must be specified.

        :param acq:
            Acquisition function to be used, defaults to Upper Confidence Bound.

        :param gp_params:
            Parameters to be passed to the Scikit-learn Gaussian Process object

        Returns
        -------
        :return: Nothing
        """
        # Reset timer   
        self.plog.reset_timer()

        # Set acquisition function
        self.util = UtilityFunction(kind=acq, kappa=kappa, z_a=z_a, z_m=z_m,
                                    z_v=z_v, xi=xi, surrogate='gp')

        # Initialize x, y and find current y_max
        if not self.initialized:           
            if self.verbose:
                self.plog.print_header()
            self.init(init_points, z_m, z_v, acq, xi)

        y_max = self.Y.max()

        ur = unique_rows(self.X) 

        # Set parameters if any was passed
        self.gp.set_params(**gp_params)       
        # Find unique rows of X to avoid GP from breaking
        ur = unique_rows(self.X)   
        gpY = self.Y - np.mean(self.Y)
        self.gp.fit(self.X[ur], self.Y[ur])
        
        x_max = acq_max(ac=self.util.utility,
                        gp=self.gp,
                        y_max=y_max,
                        bounds=self.bounds)      
        
#         print(x_max)
        if self.verbose:
            self.plog.print_header(initialization=False)
        # Iterative process of searching for the maximum. At each round the
        # most recent x and y values probed are added to the X and Y arrays
        # used to train the Gaussian Process. Next the maximum known value
        # of the target function is found and passed to the acq_max function.
        # The arg_max of the acquisition function is found and this will be
        # the next probed value of the target function in the next round.
        mean_array = [] #collecting the predicted mean of each iteration
        sigma_array = []
        for i in range(n_iter):
            # Test if x_max is repeated, if it is, draw another one at random
            # If it is repeated, print a warning
            pwarning = False
            if np.any((self.X - x_max).sum(axis=1) == 0):

                x_max = np.random.uniform(self.bounds[:, 0],
                                          self.bounds[:, 1],
                                          size=self.bounds.shape[0])

                pwarning = True

            # Append most recently generated values to X and Y arrays
#            t0=time.time()
            self.X = np.vstack((self.X, x_max.reshape((1, -1))))
            self.Y = np.append(self.Y, self.f(x_max,self.vae))
            

            ur = unique_rows(self.X)
            gpY = self.Y - np.mean(self.Y)
            self.gp.fit(self.X[ur], self.Y[ur])
            # print(i)
    
            # Update maximum value to search for next probe point.
            if self.Y[-1] > y_max:
                y_max = self.Y[-1]

            # Maximize acquisition function to find next probing point
            t0=time.time()
            x_max = acq_max(ac=self.util.utility,
                            gp=self.gp,
                            y_max=y_max,
                            bounds=self.bounds)
            
            #draw sample from gaussian process 
            #self.Y[-1] is the value of the objective function 
#             

            x_sample=np.reshape(x_max,(1,2))
            #gp parameter
            
            param = self.gp.predict(x_sample, return_std= True)
            m=param[0].ravel() # mean of gp
            v=param[1].ravel() # sigma of gp
            mean_array=np.append(mean_array,m)
            sigma_array=np.append(sigma_array,v)
            log_mean = np.exp(m+v**2/2)
            # print(m)
            # f= open("/home/mz1482/project/BOVAE (miccai2018)/gp_mean_var_entropy.txt","a")
            # f.write(str(i) + ","+str(m[0]) + "," + str(v[0]) +"\n")
            # f.close()
            # print(param[0], param[1])
            gp_sample = self.gp.sample_y(x_sample,1) #original
            # gp_sample = self.gp.sample_y(x_sample,5) #edited to see the GP plot
            gp_sample = gp_sample.ravel()
            # print(gp_sample)
        
            # plt.hist(gp_sample)
            # plt.show()
            # f= open("/home/mz1482/project/BOVAE (miccai2018)/ucb.txt","a")
            # # f.write(str(i) + ","+str(x_max[0]) + "," + str(x_max[1]) + "," + str(self.Y[-1])+","+str(gp_sample[0]) +"\n")
            # f.write(str(i) + ","+str(x_max[0]) + "," + str(x_max[1]) + "," + str(self.Y[-1]) +"\n")
            # f.close()

            
            t1=time.time()
#             print(x_max)
#            print('3. time to maximize the acquisation function '+ str(t1-t0))
            # Print stuff
    ###############very important##########
            # self.plog.print_step(self.X[-1], self.Y[-1], warning=pwarning)
            #saving optimized z
            # f= open("/home/mz1482/project/BOVAE (miccai2018)/cv.txt","a")
            # f.write(str(i) + ","+str(x_max[0]) + "," + str(x_max[1]) + "," + str(self.Y[-1]) +"\n")
            # f.close()
            if self.verbose:
                self.plog.print_step(self.X[-1], self.Y[-1], warning=pwarning)

            # Keep track of total number of iterations
            self.i += 1

            self.res['max'] = {'max_val': self.Y.max(),
                               'max_params':  self.X[self.Y.argmax()]                                                     
                               }
            self.res['all']['values'].append(self.Y[-1])
            self.res['all']['params'].append( self.X[-1])
#             print(self.Y[-1])
        #plotting the mean of whole space
        # print(m)
        # print(v**2)
        # sns.distplot(mean_array)
        exp_gpmean = np.exp(mean_array+sigma_array**2/2)
        # sns.distplot(exp_gpmean)
        # sns.distplot(np.exp(mean_array))
        # Print a final report if verbose active.
#         print(self.X[self.Y.argmax()])
        if self.verbose:
            self.plog.print_summary()



    def maxi(self,
                 init_points=5,
                 n_iter=25,
                 acq='ei',
                 kappa=2.576,
                 z_a=1,
                 z_m=0,
                 z_v=1,
                 xi=0.0,
                 Z=np.array([0,0]),
                 f_exact=np.array([0]),
                 **gp_params):

        # Reset timer   
        self.plog.reset_timer()

        # Set acquisition function
        self.util = UtilityFunction(kind=acq, kappa=kappa, z_a=z_a, z_m=z_m,
                                    z_v=z_v, xi=xi, surrogate='gp')

        # Initialize x, y and find current y_max
        if not self.initialized:           
            if self.verbose:
                self.plog.print_header()
            self.init(init_points, z_m, z_v, acq, xi)

        y_max = self.Y.max()

        ur = unique_rows(self.X) 

        # Set parameters if any was passed
        self.gp.set_params(**gp_params)       
        # Find unique rows of X to avoid GP from breaking
        ur = unique_rows(self.X)   
        gpY = self.Y - np.mean(self.Y)
        self.gp.fit(self.X[ur], self.Y[ur])
        
        x_max = acq_max(ac=self.util.utility,
                        gp=self.gp,
                        y_max=y_max,
                        bounds=self.bounds)      
        
#         print(x_max)
        if self.verbose:
            self.plog.print_header(initialization=False)
        # Iterative process of searching for the maximum. At each round the
        # most recent x and y values probed are added to the X and Y arrays
        # used to train the Gaussian Process. Next the maximum known value
        # of the target function is found and passed to the acq_max function.
        # The arg_max of the acquisition function is found and this will be
        # the next probed value of the target function in the next round.
        mean_array = [] #collecting the predicted mean of each iteration
        sigma_array = []
        kl_array=[]
        iteration=[]
        for i in range(n_iter):
            # Test if x_max is repeated, if it is, draw another one at random
            # If it is repeated, print a warning
            pwarning = False
            if np.any((self.X - x_max).sum(axis=1) == 0):

                x_max = np.random.uniform(self.bounds[:, 0],
                                          self.bounds[:, 1],
                                          size=self.bounds.shape[0])

                pwarning = True

            # Append most recently generated values to X and Y arrays
#            t0=time.time()
            self.X = np.vstack((self.X, x_max.reshape((1, -1))))
            self.Y = np.append(self.Y, self.f(x_max,self.vae))
            

            ur = unique_rows(self.X)
            gpY = self.Y - np.mean(self.Y)
            self.gp.fit(self.X[ur], self.Y[ur])
            # print(i)
    
            # Update maximum value to search for next probe point.
            if self.Y[-1] > y_max:
                y_max = self.Y[-1]

            # Maximize acquisition function to find next probing point
            t0=time.time()
            x_max = acq_max(ac=self.util.utility,
                            gp=self.gp,
                            y_max=y_max,
                            bounds=self.bounds)
            
            #draw sample from gaussian process 
            #self.Y[-1] is the value of the objective function 
#             

            x_sample=np.reshape(x_max,(1,2))
            #gp parameter
            
            param = self.gp.predict(x_sample, return_std= True)
            m=param[0].ravel() # mean of gp
            v=param[1].ravel() # sigma of gp
            mean_array=np.append(mean_array,m)
            sigma_array=np.append(sigma_array,v)
            log_mean = np.exp(m+v**2/2)
            # print(m)
            # f= open("/home/mz1482/project/BOVAE (miccai2018)/exp_gpmean_ev.txt","a")
            # f.write(str(i) + ","+str(x_max[0]) + "," + str(x_max[1]) + "," + str(log_mean[0]) +"\n")
            # f.close()
            # print(param[0], param[1])
            gp_sample = self.gp.sample_y(x_sample,1) #original
            # gp_sample = self.gp.sample_y(x_sample,5) #edited to see the GP plot
            gp_sample = gp_sample.ravel()
            # print(gp_sample)
        
            # plt.hist(gp_sample)
            # plt.show()
            # f= open("/home/mz1482/project/BOVAE (miccai2018)/ucb.txt","a")
            # # f.write(str(i) + ","+str(x_max[0]) + "," + str(x_max[1]) + "," + str(self.Y[-1])+","+str(gp_sample[0]) +"\n")
            # f.write(str(i) + ","+str(x_max[0]) + "," + str(x_max[1]) + "," + str(self.Y[-1]) +"\n")
            # f.close()

            
            t1=time.time()
            if self.verbose:
                self.plog.print_step(self.X[-1], self.Y[-1], warning=pwarning)

            # Keep track of total number of iterations
            self.i += 1

            self.res['max'] = {'max_val': self.Y.max(),
                               'max_params':  self.X[self.Y.argmax()]                                                     
                               }
            self.res['all']['values'].append(self.Y[-1])
            self.res['all']['params'].append( self.X[-1])
            # if i%20==0:
            if i==100:
                z1=Z[:,0]
                z2=Z[:,1]
                realf=f_exact
                zfix=np.random.normal(loc=0,scale=.01,size=2)
                accepted_f = []
                z1_new = []
                z2_new = []
                m_new = []
                index= []
                for j in range(2500):
                    x_0=np.reshape(zfix,(1,2))
                    param = self.gp.predict(x_0, return_std= True)
                    m=param[0].ravel() # mean of gp
                    v=param[1].ravel() # sigma of gp
                    if m <-1:
                        log_mean_0 = np.exp(m+v**2/2)
                        z_star = zfix + np.random.normal(loc = 0, scale = 0.5,size=2)
                        z_star2 = np.reshape(z_star,(1,2))
                        param2 = self.gp.predict(z_star2, return_std= True)
                        m2=param2[0].ravel() # mean of gp
                        v2=param2[1].ravel() # sigma of gp
                        log_mean_2 = np.exp(m2+v2**2/2)
                        rho = min(1, log_mean_2/log_mean_0)
                        r=np.random.rand()
                        if r < rho:
                            # f= open("/home/mz1482/project/BOVAE (miccai2018)/exp(gp)_entropy.txt","a")
                            # f.write(str(z_star[0]) + "," + str(z_star[1]) + "," + str(log_mean_2[0]) +"\n")
                            # f.close()
                            zfix = z_star
                            # samples = np.append(samples, [z], axis=0)
                            # f=np.append(f,b)
                            accepted_f=np.append(accepted_f,log_mean_2)
                            # proposef=np.append(proposef,log_mean) #based on log normal
                            z1_new = np.append(z1_new,z_star[0])
                            z2_new = np.append(z2_new,z_star[1])
                            m_new = np.append(m_new,m)
                            index = np.append(index,j)

                    # proposef=np.append(proposef,m) #mean of gp
                # kl=np.sum(np.log(accepted_f/proposef))/len(proposef)
                # ar = len(accepted_f)/len(realf)
                # print(ar)
                # print(kl)
                # kl_array = np.append(kl_array,kl)
                # iteration = np.append(iteration,i)
                exp_gp_data = np.column_stack((z1_new,z2_new,accepted_f))
                ar=len(accepted_f)/(j+1)
                print("iteration no is ",i)
                print("acceptance rate", ar)
                # print("mean of gp", np.mean(m_new))
                # plt.scatter(index,m_new)
                plt.scatter(z1,realf,facecolor='red')
                plt.scatter(z1_new,accepted_f,facecolor='green')
                plt.show()
            # for j in range(len(Z)):
            #     x_sample=np.reshape(Z[j],(1,2))
            #     #gp parameter
            #     param = self.gp.predict(x_sample, return_std= True)
            #     m=param[0].ravel() # mean of gp
            #     v=param[1].ravel() # sigma of gp
            #     log_mean = np.exp(m+v**2/2)
            #     proposef=np.append(proposef,log_mean) #based on log normal
            #     # proposef=np.append(proposef,m) #mean of gp
            # kl=np.sum(np.log(realf/proposef))/len(Z)
            # # print(kl)
            # kl_array = np.append(kl_array,kl)
            # iteration = np.append(iteration,i)
            # if i%30==0:
            #     print("iteration no is ",i)
            #     plt.scatter(z1,realf,facecolor='red')
            #     plt.scatter(z1,proposef,facecolor='green')
            #     plt.show()
        # plt.plot(iteration,kl_array)
        # plt.xlabel('iteration')
        # plt.ylabel('KL divergence')
        # plt.show()

            

        exp_gpmean = np.exp(mean_array+sigma_array**2/2)
        if self.verbose:
            self.plog.print_summary()
        # realf=f_exact
        # proposef=[]
        # for j in range(len(Z)):
        #     x_sample=np.reshape(Z[j],(1,2))
        #     #gp parameter
        #     param = self.gp.predict(x_sample, return_std= True)
        #     m=param[0].ravel() # mean of gp
        #     v=param[1].ravel() # sigma of gp
        #     log_mean = np.exp(m+v**2/2)
        #     proposef=np.append(proposef,log_mean)
        #     # f= open("/home/mz1482/project/BOVAE (miccai2018)/log_mean_cv.txt","a")
        #     # f.write(str(j) + ","+str(Z[j,0]) + "," + str(Z[j,1]) + "," + str(log_mean[0]) +"\n")
        #     # f.close()
        #     # print(log_mean)
        # print(np.sum(realf))
        # print(realf.shape)
        # kl=np.sum(np.log(realf/proposef))/len(Z)
        # print(kl)
        return exp_gp_data


    def max_kl(self,
                 init_points=5,
                 n_iter=25,
                 acq='ei',
                 kappa=2.576,
                 z_a=1,
                 z_m=0,
                 z_v=1,
                 xi=0.0,
                 Z=np.array([0,0]),
                 f_exact=np.array([0]),
                 **gp_params):

        # Reset timer   
        self.plog.reset_timer()

        # Set acquisition function
        self.util = UtilityFunction(kind=acq, kappa=kappa, z_a=z_a, z_m=z_m,
                                    z_v=z_v, xi=xi, surrogate='gp')

        # Initialize x, y and find current y_max
        if not self.initialized:           
            if self.verbose:
                self.plog.print_header()
            self.init(init_points, z_m, z_v, acq, xi)

        y_max = self.Y.max()

        ur = unique_rows(self.X) 

        # Set parameters if any was passed
        self.gp.set_params(**gp_params)       
        # Find unique rows of X to avoid GP from breaking
        ur = unique_rows(self.X)   
        gpY = self.Y - np.mean(self.Y)
        self.gp.fit(self.X[ur], self.Y[ur])
        
        x_max = acq_max(ac=self.util.utility,
                        gp=self.gp,
                        y_max=y_max,
                        bounds=self.bounds)      
        
#         print(x_max)
        if self.verbose:
            self.plog.print_header(initialization=False)
        # Iterative process of searching for the maximum. At each round the
        # most recent x and y values probed are added to the X and Y arrays
        # used to train the Gaussian Process. Next the maximum known value
        # of the target function is found and passed to the acq_max function.
        # The arg_max of the acquisition function is found and this will be
        # the next probed value of the target function in the next round.
        mean_array = [] #collecting the predicted mean of each iteration
        sigma_array = []
        kl_array=[]
        iteration=[]
        for i in range(n_iter):
            # Test if x_max is repeated, if it is, draw another one at random
            # If it is repeated, print a warning
            pwarning = False
            if np.any((self.X - x_max).sum(axis=1) == 0):

                x_max = np.random.uniform(self.bounds[:, 0],
                                          self.bounds[:, 1],
                                          size=self.bounds.shape[0])

                pwarning = True

            # Append most recently generated values to X and Y arrays
#            t0=time.time()
            self.X = np.vstack((self.X, x_max.reshape((1, -1))))
            self.Y = np.append(self.Y, self.f(x_max,self.vae))
            

            ur = unique_rows(self.X)
            gpY = self.Y - np.mean(self.Y)
            self.gp.fit(self.X[ur], self.Y[ur])
            # print(i)
    
            # Update maximum value to search for next probe point.
            if self.Y[-1] > y_max:
                y_max = self.Y[-1]

            # Maximize acquisition function to find next probing point
            t0=time.time()
            x_max = acq_max(ac=self.util.utility,
                            gp=self.gp,
                            y_max=y_max,
                            bounds=self.bounds)
            
            #draw sample from gaussian process 
            #self.Y[-1] is the value of the objective function 
#             

            x_sample=np.reshape(x_max,(1,2))
            #gp parameter
            
            param = self.gp.predict(x_sample, return_std= True)
            # m=param[0].ravel() # mean of gp
            # v=param[1].ravel() # sigma of gp
            # log_mean = np.exp(m+v**2/2)
            # gp_sample = self.gp.sample_y(x_sample,1) #original
            # gp_sample = self.gp.sample_y(x_sample,5) #edited to see the GP plot
            # gp_sample = gp_sample.ravel()

            
            t1=time.time()
            if self.verbose:
                self.plog.print_step(self.X[-1], self.Y[-1], warning=pwarning)

            # Keep track of total number of iterations
            self.i += 1

            self.res['max'] = {'max_val': self.Y.max(),
                               'max_params':  self.X[self.Y.argmax()]                                                     
                               }
            self.res['all']['values'].append(self.Y[-1])
            self.res['all']['params'].append( self.X[-1])
            # # if i%20==0:
            # if i==100:
            z1=Z[:,0]
            z2=Z[:,1]
            realf=f_exact
            zfix=np.random.normal(loc=0,scale=.01,size=2)
            accepted_f = []
            z1_new = []
            z2_new = []
            m_new = []
            index= []
            for j in range(2500):
                x_0=np.reshape(zfix,(1,2))
                param = self.gp.predict(x_0, return_std= True)
                m=param[0].ravel() # mean of gp
                v=param[1].ravel() # sigma of gp
                if m <-1:
                    log_mean_0 = np.exp(m+v**2/2)
                    z_star = zfix + np.random.normal(loc = 0, scale = 0.5,size=2)
                    z_star2 = np.reshape(z_star,(1,2))
                    param2 = self.gp.predict(z_star2, return_std= True)
                    m2=param2[0].ravel() # mean of gp
                    v2=param2[1].ravel() # sigma of gp
                    log_mean_2 = np.exp(m2+v2**2/2)
                    rho = min(1, log_mean_2/log_mean_0)
                    r=np.random.rand()
                    if r < rho:
                        zfix = z_star
                        accepted_f=np.append(accepted_f,log_mean_2)
                        # proposef=np.append(proposef,log_mean) #based on log normal
                        z1_new = np.append(z1_new,z_star[0])
                        z2_new = np.append(z2_new,z_star[1])
                        # m_new = np.append(m_new,m)
                        index = np.append(index,j)

                # proposef=np.append(proposef,m) #mean of gp
            # kl=np.sum(np.log(accepted_f/proposef))/len(proposef)
            # ar = len(accepted_f)/len(realf)
            # print(ar)
            # print(kl)
            # kl_array = np.append(kl_array,kl)
            # iteration = np.append(iteration,i)
            exp_gp_data = np.column_stack((z1_new,z2_new,accepted_f))
            ar=len(accepted_f)/(j+1)
            print("iteration no is ",i)
            print("acceptance rate", ar)
            # print("mean of gp", np.mean(m_new))
            # plt.scatter(index,m_new)
            plt.scatter(z1,realf,facecolor='red')
            plt.scatter(z1_new,accepted_f,facecolor='green')
            plt.show()
            # for j in range(len(Z)):
            #     x_sample=np.reshape(Z[j],(1,2))
            #     #gp parameter
            #     param = self.gp.predict(x_sample, return_std= True)
            #     m=param[0].ravel() # mean of gp
            #     v=param[1].ravel() # sigma of gp
            #     log_mean = np.exp(m+v**2/2)
            #     proposef=np.append(proposef,log_mean) #based on log normal
            #     # proposef=np.append(proposef,m) #mean of gp
            # kl=np.sum(np.log(realf/proposef))/len(Z)
            # # print(kl)
            # kl_array = np.append(kl_array,kl)
            # iteration = np.append(iteration,i)
            # if i%30==0:
            #     print("iteration no is ",i)
            #     plt.scatter(z1,realf,facecolor='red')
            #     plt.scatter(z1,proposef,facecolor='green')
            #     plt.show()
        # plt.plot(iteration,kl_array)
        # plt.xlabel('iteration')
        # plt.ylabel('KL divergence')
        # plt.show()

            

        exp_gpmean = np.exp(mean_array+sigma_array**2/2)
        if self.verbose:
            self.plog.print_summary()
        # realf=f_exact
        # proposef=[]
        # for j in range(len(Z)):
        #     x_sample=np.reshape(Z[j],(1,2))
        #     #gp parameter
        #     param = self.gp.predict(x_sample, return_std= True)
        #     m=param[0].ravel() # mean of gp
        #     v=param[1].ravel() # sigma of gp
        #     log_mean = np.exp(m+v**2/2)
        #     proposef=np.append(proposef,log_mean)
        #     # f= open("/home/mz1482/project/BOVAE (miccai2018)/log_mean_cv.txt","a")
        #     # f.write(str(j) + ","+str(Z[j,0]) + "," + str(Z[j,1]) + "," + str(log_mean[0]) +"\n")
        #     # f.close()
        #     # print(log_mean)
        # print(np.sum(realf))
        # print(realf.shape)
        # kl=np.sum(np.log(realf/proposef))/len(Z)
        # print(kl)
        return exp_gp_data


        

    def points_to_csv(self, file_name):
        """
        After training all points for which we know target variable
        (both from initialization and optimization) are saved

        :param file_name: name of the file where points will be saved in the csv
            format

        :return: None
        """
        points = np.hstack((self.X, np.expand_dims(self.Y, axis=1)))
        header = ', '.join(self.keys + ['target'])
        np.savetxt(file_name, points, header=header, delimiter=',')
        
