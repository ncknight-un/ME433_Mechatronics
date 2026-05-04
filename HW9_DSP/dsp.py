import csv
import matplotlib.pyplot as plt # for plotting
import numpy as np # for sine function

t = [] # column 0
data1 = [] # column 1
data2 = [] # column 2

# Extract the Data from the File:
with open('sigD.csv') as f:
    # open the csv file
    reader = csv.reader(f)
    for row in reader:
        # read the rows 1 one by one
        t.append(float(row[0])) # leftmost column
        data1.append(float(row[1])) # second column

        # If a third column exists:
        if len(row) > 2:
            data2.append(float(row[2]))

# Get the Sample rate of the data: 
sample_rate = len(data1) / data1[-1]
print(f"The sampling rate is {sample_rate}")

# Plot the Data:
plt.plot(t,data1,'b-*')
plt.xlabel('Time [s]')
plt.ylabel('Signal')
plt.title('Signal vs Time')
plt.show()

# Part 4) Plot the FFT of the Signal Data:
# ______________________________________________________________________________________________
Fs = sample_rate # sample rate
Ts = 1.0/Fs # sampling interval
ts = np.arange(0,t[-1],Ts) # time vector
y = data1 # the data to make the fft from
n = len(y) # length of the signal
k = np.arange(n)
T = n/Fs
frq = k/T # two sides frequency range
frq = frq[range(int(n/2))] # one side frequency range
Y = np.fft.fft(y)/n # fft computing and normalization
Y = Y[range(int(n/2))]

# Plot the FFT for the original data and the LPF data:
fig, (ax1, ax2) = plt.subplots(2, 1)
ax1.plot(t,y,'g')
ax1.set_xlabel('Time')
ax1.set_ylabel('Amplitude')
# Plot of the FFT:
ax2.loglog(frq,abs(Y),'k')
ax2.set_xlabel('Freq (Hz)')
ax2.set_ylabel('|Y(freq)|')
ax2.set_title('FFT')
plt.show()


# Part 5) Apply a Low Pass Filter to the Data using a Moving Average:
# ______________________________________________________________________________________________
data1_LPMV = []   # Low Pass Filter List
x_history = 100  # Number of points in the past to be averaged in LPF
for idx in range(len(data1)):
    if idx < x_history:
        data1_LPMV.append(data1[idx])
    else: 
        sum = 0
        for past_id in range(x_history):
            sum += data1[idx - past_id]
        sum /= x_history
        # Add the average to the new list:
        data1_LPMV.append(sum)

# Get the FFT of the Filtered data:
y2= data1_LPMV # the data to make the fft from that is filtered
Y2 = np.fft.fft(y2)/n # fft computing and normalization
Y2 = Y2[range(int(n/2))]

# Plot the FFT for the original data and the LPF data:
fig, (ax1, ax2) = plt.subplots(2, 1)
ax1.plot(t,data1_LPMV,'g')
ax1.set_xlabel('Time')
ax1.set_ylabel('Amplitude')
# Plot of the FFT:
ax2.loglog(frq,abs(Y),'k')
ax2.loglog(frq,abs(Y2),'r')
ax2.set_xlabel('Freq (Hz)')
ax2.set_ylabel('|Y(freq)|')
ax2.set_title(f'LPF - {x_history} past-averaged')
plt.show()


# Part 6) Apply Low Pass Filtering with IIR: 
# ______________________________________________________________________________________________
A = 0.95
B = 1 - A
data1_LPIIR = []   # Low Pass Filter List for IIR
for idx in range(len(data1)):
    if idx ==  0:
        data1_LPIIR.append(A * 0 + B * data1[idx])
    else: 
        data1_LPIIR.append(A * data1_LPIIR[idx - 1] + B * data1[idx])

# Get the FFT of the Filtered data:
y2= data1_LPIIR # the data to make the fft from that is filtered
Y2 = np.fft.fft(y2)/n # fft computing and normalization
Y2 = Y2[range(int(n/2))]

# Plot the FFT for the original data and the LPF data:
fig, (ax1, ax2) = plt.subplots(2, 1)
ax1.plot(t,data1_LPIIR,'g')
ax1.set_xlabel('Time')
ax1.set_ylabel('Amplitude')
# Plot of the FFT:
ax2.loglog(frq,abs(Y),'k')
ax2.loglog(frq,abs(Y2),'r')
ax2.set_xlabel('Freq (Hz)')
ax2.set_ylabel('|Y(freq)|')
ax2.set_title(f'LPF - A = {A} & B = {B}')
plt.show()


# Part 7) Applying a Low Pass Sinc Filter:
# ______________________________________________________________________________________________
# Modeled weights for FIR using Website: https://fiiir.com/
weights = [
    0.016475920282948690,
    0.017054204224753452,
    0.017617052667658336,
    0.018163183173519573,
    0.018691346589453775,
    0.019200330501115824,
    0.019688962591300284,
    0.020156113893671546,
    0.020600701931734123,
    0.021021693733492330,
    0.021418108712617286,
    0.021789021407337010,
    0.022133564068691849,
    0.022450929090250545,
    0.022740371271860769,
    0.023001209910510589,
    0.023232830711902033,
    0.023434687516883282,
    0.023606303837450455,
    0.023747274197611152,
    0.023857265274998492,
    0.023936016839734148,
    0.023983342487660070,
    0.023999130165688807,
    0.023983342487660070,
    0.023936016839734148,
    0.023857265274998492,
    0.023747274197611152,
    0.023606303837450455,
    0.023434687516883282,
    0.023232830711902033,
    0.023001209910510589,
    0.022740371271860769,
    0.022450929090250545,
    0.022133564068691849,
    0.021789021407337010,
    0.021418108712617286,
    0.021021693733492330,
    0.020600701931734123,
    0.020156113893671546,
    0.019688962591300284,
    0.019200330501115824,
    0.018691346589453775,
    0.018163183173519573,
    0.017617052667658336,
    0.017054204224753452,
    0.016475920282948690
]

# Calculate the Cuttoff Freq Normalized: 
norm_cutoff_f = 100 / sample_rate
print(f"The normalized cutoff frequency is {norm_cutoff_f}")

# Print the Transition Bandwidth Used:
trans_band = 0.02
print(f"The Transition Bandwidth is {trans_band}")

# New Array to hold FIR Filtered Data:
data1_FIR = []

# Apply the Weights to the Signal:
for idx in range(len(data1)):
    y = 0
    # Loop over the number of weights and apply to the signal:
    for k in range(len(weights)):
        if idx - k >= 0:
            y += weights[k] * data1[idx - k]
    data1_FIR.append(y)

# Get the FFT of the Filtered data using FIR:
y2= data1_FIR # the data to make the fft from that is filtered
Y2 = np.fft.fft(y2)/n # fft computing and normalization
Y2 = Y2[range(int(n/2))]

# Plot the FFT for the original data and the LPF data:
fig, (ax1, ax2) = plt.subplots(2, 1)
ax1.plot(t,data1_FIR,'g')
ax1.set_xlabel('Time')
ax1.set_ylabel('Amplitude')
# Plot of the FFT:
ax2.loglog(frq,abs(Y),'k')
ax2.loglog(frq,abs(Y2),'r')
ax2.set_xlabel('Freq (Hz)')
ax2.set_ylabel('|Y(freq)|')
ax2.set_title(f'FIR - #weights = {len(weights)}, fL = {norm_cutoff_f}, bL = {trans_band}')
plt.show()
