#!/usr/bin/env python
"""
@author: Jiawei Qiu
Based on `RohdeSchwarz_SpectrumAnalyzer` driver.
"""
from VISA_Driver import VISA_Driver
import numpy as np

__version__ = "0.0.2"

class Error(Exception):
    pass

class Driver(VISA_Driver):
    """ This class implements the Rohde&Schwarz Network Analyzer driver"""

    def performOpen(self, options={}):
        """Perform the operation of opening the instrument connection"""
        # Calling the generic VISA open to make sure we have a connection
        VISA_Driver.performOpen(self, options=options)

    def performClose(self, bError=False, options={}):
        """Perform the close instrument connection operation"""
        # Calling the generic VISA class to close communication
        VISA_Driver.performClose(self, bError, options=options)


    def performSetValue(self, quant, value, sweepRate=0.0, options={}):
        """Perform the Set Value instrument operation. This function should
        return the actual value set by the instrument"""
        if quant.name in ('Wait for new trace',):
            # do nothing
            pass
        elif quant.name in ('Range type'):
            if value in ('Center - Span', 'Start - Stop'):
                self.writeAndLog('SENSe:LIST:POWer:STATe OFF;:INIT:CONT ON')
            elif value in ('Single', 'List'):
                self.writeAndLog('SENSe:LIST:POWer:SET OFF,ON,OFF,IMM,POS,0,0')
        else:
            # run standard VISA case
            value = VISA_Driver.performSetValue(self, quant, value, sweepRate, options)
        return value


    def performGetValue(self, quant, options={}):
        """Perform the Get Value instrument operation"""
        # Check type of quantity
        if quant.name in ('Signal',):
            # Turn off list measure mode.
            # self.writeAndLog('SENSe:LIST:POWer:STATe OFF;:INIT:CONT ON')
            bWaitTrace = self.getValue('Wait for new trace')
            bAverage = self.getValue('Average')
            if bWaitTrace:
                if bAverage:
                    nAverage = self.getValue('# of averages')
                    # self.writeAndLog(':SENS:AVER:CLE;:ABOR;:INIT;*WAI')
                    self.writeAndLog(':ABOR;:INIT:CONT OFF;:SENS:AVER:COUN %d;:INIT:IMM;*OPC' % nAverage)
                else:
                    self.writeAndLog(':ABOR;:INIT:CONT OFF;:SENS:AVER:COUN 1;:INIT:IMM;*OPC')
                # Wait some time before first check
                self.wait(0.03)
                bDone = False
                while (not bDone) and (not self.isStopped()):
                    # check if done
                    if bAverage:
                        # sAverage = self.askAndLog('SENS:AVER:COUN:CURR?')
                        # bDone = (int(sAverage) >= nAverage)
                        stb = int(self.askAndLog('*ESR?'))
                        bDone = (stb & 1) > 0
                    else:
                        stb = int(self.askAndLog('*ESR?'))
                        bDone = (stb & 1) > 0
                    if not bDone:
                        self.wait(0.1)
                # if stopped, don't get data
                if self.isStopped():
                    self.writeAndLog('*CLS;:INIT:CONT ON;')
                    return []
            # get data as float32, convert to numpy array
            self.writeAndLog(':FORM REAL,32;TRAC? TRACE1')
            sData = self.read(ignore_termination=True)
            if bWaitTrace and not bAverage:
                self.writeAndLog(':INIT:CONT ON;')
            # strip header to find # of points
            i0 = sData.find(b'#')
            nDig = int(sData[i0+1:i0+2])
            nByte = int(sData[i0+2:i0+2+nDig])
            nData = int(nByte/4)
            # get data to numpy array
            vData = np.frombuffer(sData[(i0+2+nDig):(i0+2+nDig+nByte)], 
                                    dtype='<f', count=nData)
            startFreq = self.readValueFromOther('Start frequency')
            stopFreq = self.readValueFromOther('Stop frequency')
            # create a trace dict
            value = quant.getTraceDict(vData, x0=startFreq, x1=stopFreq)
        elif quant.name in ('List values',):
            # Enable list measurement mode, and define constant settings.
            # the parameters OFF,ON,OFF disable peak and averange measure, enable RMS measure.
            # self.writeAndLog('SENSe:LIST:POWer:SET OFF,ON,OFF,IMM,POS,0,0')
            message = 'SENSe:LIST:POWer? '
            x = []
            for freq in (self.getValue('List point 1'), self.getValue('List point 2'), self.getValue('List point 3')):
                message = message + (f'{freq}Hz,'
                                    f'{self.getValue("Reference level")}dBm,'
                                    f'{self.getValue("RF input attenuation (zero span)")}dB,'
                                    f'OFF,NORM,'
                                    f'{self.getValue("Res bandwidth")}Hz,'
                                    f'{self.getValue("Video bandwidth (zero span)")}Hz,'
                                    f'{self.getValue("Measurement time")}s,0,')
                x.append(freq)
            message = message[:-1] #removing the last comma.
            sData = self.askAndLog(message)
            vData = np.fromstring(sData, dtype=float, sep=',')
            value = quant.getTraceDict(vData, x=x)
        elif quant.name in ('Measured power',):
            # turn on the list measuerment mode
            # self.writeAndLog('SENSe:LIST:POWer:SET OFF,ON,OFF,IMM,POS,0,0')
            message = ('SENSe:LIST:POWer? '
                      f'{self.getValue("Frequency")}Hz,'
                      f'{self.getValue("Reference level")}dBm,'
                      f'{self.getValue("RF input attenuation (zero span)")}dB,'
                      f'OFF,NORM,'
                      f'{self.getValue("Res bandwidth")}Hz,'
                      f'{self.getValue("Video bandwidth (zero span)")}Hz,'
                      f'{self.getValue("Measurement time")}s,0')
            sData = self.askAndLog(message)
            vData = float(sData)
            value = vData
        elif quant.name in ('Wait for new trace',):
            # do nothing, return local value
            value = quant.getValue()
        else:
            # for all other cases, call VISA driver
            value = VISA_Driver.performGetValue(self, quant, options)
        return value
        


if __name__ == '__main__':
    pass
