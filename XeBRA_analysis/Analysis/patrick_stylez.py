import matplotlib.pyplot as plt
from matplotlib.ticker import AutoMinorLocator

def styles():
    
    fig=plt.figure(figsize=(18, 13), dpi=150)
    plt.rc('font', family='serif')
    plt.rc('axes', titlesize=25)
    plt.rc('axes', labelsize=25)
    label_size = 25 #25
    label_pad = 13 #10
    title_size = 39 #30
    title_pad = 26 #20
    axes = plt.gca()
    axes.tick_params(axis='both')
    for axis in ['top', 'bottom', 'left', 'right']:
        axes.spines[axis].set_linewidth(2.2)
    axes.xaxis.set_minor_locator(AutoMinorLocator(5)) 
    plt.tick_params(which='minor', direction='in', labelsize=label_size, top=True, right=True, width=1.2, length=6)
    axes.yaxis.set_minor_locator(AutoMinorLocator(5))
    plt.tick_params(which='minor', direction='in', labelsize=label_size, top=True, right=True, width=1.2, length=6)
    plt.tick_params(which='major', direction='in', labelsize=label_size, top=True, right=True, width=1.2, length=12)
    return fig, axes