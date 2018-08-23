# PMT-calibration

# Code in this folder is explained below:

- Delete_mongo_collection:
  By inserting a specific collection name, one can delete it
  (Mongo string and PMT channel can be changed)
  
- Waveforms:
  Shows simple waveforms for selected collection and selected PMT channel 
  
- LED_calibration_integrator:
  consists of several parts; first of all, the raw waveform data is taken. 
  _check_rms and _calc_baseline are basis function to constrain waveforms.
  The integration function sums up data in a specific time window where we expect a signal
  Before fitting the data, we first get a basic histrogram of the integrated data, to check whether the data make sense or not. 
  Next a few parameter definitions are given. For example: where do we expect the SPE? This makes the fit more flexible.
  Since we expect the integrated spectrum to consist of 5 different gaussians, a penta_gaus function is defined.
  Now we fit the data by using the defined gaussian plus the fit parameters plus boundaries. The output plot also shows each gaussian seperately. 
  There is also a statistical error included.
  The output value is then the gain of the PMT (mu_SPE) +/- the standard deviation on mu_SPE extracted of the cov. matrix.
  
LED_calibration_with_pax:
  Returns data processed by pax and fits them. 

voltage_gain_plot:
  shows the gain of each PMT as a function of the bias voltage in a single plot.  You first need the gains for that since the values are hard-coded. (really basic code)

Expo_fit:
  This code is needed to fit the "gain over bias voltage" curve. Like this you can determine which voltage you need to optain a fixed gain. Formular is given.
  You also get the fitted plot plus the residuals. 
  