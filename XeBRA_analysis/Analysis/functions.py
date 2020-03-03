from scipy.stats import chi2 
import numpy as np
import matplotlib.pyplot as plt

def CutCondition(waveform):  
    FirstPeak_area = sum(waveform[:15])
    SecondPeak_area = sum(waveform[15:])    
    if  FirstPeak_area > 80 and FirstPeak_area < 500 and SecondPeak_area > 30 and SecondPeak_area  < 200:
#         print(FirstPeak_area)
#         print(SecondPeak_area)
        return(True)
    else:
        return(False)
    
    
def CutCondition_strict(waveform, integral, width):  
    FirstPeak_area = sum(waveform[:15])
    SecondPeak_area = sum(waveform[15:])
    FirstPeak_maximum = max(waveform[:15])
    SecondPeak_maximum = max(waveform[15:])
    SecondPeak_index = np.where(waveform == SecondPeak_maximum)
    SecondPeak_index_left = SecondPeak_index[0][0] -1
    SecondPeak_index_right = SecondPeak_index[0][0] +1
    SecondPeak_maximum_left = waveform[SecondPeak_index_left]
    SecondPeak_maximum_right = waveform[SecondPeak_index_right]


    if  FirstPeak_area > 100 and FirstPeak_area < 500 and SecondPeak_area > 40 and SecondPeak_area  < 200 \
    and SecondPeak_maximum < 0.5 * FirstPeak_maximum \
    and SecondPeak_maximum > 0.25 * FirstPeak_maximum \
    and SecondPeak_maximum > waveform[SecondPeak_index_left] \
    and SecondPeak_maximum > waveform[SecondPeak_index_right] \
    : 
        return(True)
    else:
        return(False)
    

    
    
def Average(lst): 
    return sum(lst) / len(lst)
    
def poisson_interval(k, alpha=0.318):
    a = alpha
    low, high = (chi2.ppf(a/2, 2*k) / 2, chi2.ppf(1-a/2, 2*k + 2) / 2)
    if k == 0:
        low = 0.0
    low_interval = k - low
    high_interval = high - k
    return low_interval, high_interval

def log_gaus(x, h, mu, sigma):

    log_gaus = h * np.exp(-(np.log(x)-mu)**2         /(2*sigma**2))
    return log_gaus

def log_fit( x, a, mu, sigma ):
    return a / x * 1. / (sigma * np.sqrt( 2. * np.pi ) ) * np.exp( -( np.log( x ) - mu )**2 / ( 2. * sigma**2 ) )

def gaus(x, h, mu, sigma):

    gaus = h * np.exp(-(x-mu)**2         /(2*sigma**2))
    return gaus

def expo(x, a, b):
    return a*np.exp(-b*x)

def linear(x,m,c):
    linear = m*x+c  
    return linear

def linear_negative(x,m,c):
    linear = m*(-x)+c  
    return linear_negative

def s1_correction(z):
    return (-0.0069 *z + 0.76)

def drifttime_to_z(t,ai, bi):
    return ai * t + bi

def S2_found(integral, width):
    #maximum_S2 = max(waveform)
    if integral > 500 and width >200 and width < 2000:
        return True
    else:
        return False
    
def PrintWaveform(waveform,i):

    fig, (ax1,ax2,ax3,ax4,ax5) = plt.subplots(1, 5, sharex=False, figsize=(15, 3.5))

    ax1.plot(waveform[i])
    ax2.plot(waveform[i+1])
    ax3.plot(waveform[i+2])
    ax4.plot(waveform[i+3])
    ax5.plot(waveform[i+4])
#     ax1.set_xlim([0, 50])
    plt.show()