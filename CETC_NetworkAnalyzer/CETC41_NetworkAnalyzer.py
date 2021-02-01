#!/usr/bin/env python
"""
@author: Jiawei Qiu
@author: Ji Chu
"""
from VISA_Driver import VISA_Driver  # pylint: disable=import-error
import numpy as np

__version__ = "2.0"

# In the instrument are several attributes about measurement: 
# window (窗口), channel (通道), measurement (测量), parameter (参数), trace (轨迹)
# `Parameter` is the S21, S11, specifying what parameter is measured.
# A parameter is always contained in a `measurement`, who has a name and 
# further grouped as `channel`. Name and parameter of all measurements
# can be queried by cmd 'CALC:PAR:CAT?'.
# `Window` and `trace` are notion about display on NA front panel. Where a window 
# may contain multiple traces, and each of them relates to a `parameter`.

# TODO: Induce memory overflow? error on instrument after long-time running.
# which does not appear on Matlab code writing cmd with fprintf.

class Error(Exception):
    pass

class Driver(VISA_Driver):
    """ This class implements the CETC41 Network Analyzer driver"""

    def performOpen(self, options={}):
        """Perform the operation of opening the instrument connection"""
        # init meas param dict
        self.dMeasParam = {}
        # calling the generic VISA open to make sure we have a connection
        VISA_Driver.performOpen(self, options=options)

    def performSetValue(self, quant, value, sweepRate=0.0, options={}):
        """Perform the Set Value instrument operation. This function should
        return the actual value set by the instrument"""
        if quant.name == 'S11 - Enabled':
            if value is True:
                # TODO: Strange block
                del_name='CH1_WIN1_LINE1_PARAM1'
                newName = 'LabC_S11'
            else:
                del_name= 'LabC_S11'
                newName = 'CH1_WIN1_LINE1_PARAM1'
            self.writeAndLog("CALC:PAR:DEL '%s'" % del_name )  # Delete the default measurement.
            self.writeAndLog("CALC:PAR:DEF '%s',%s" % (newName, 'S11'))  # Replace it with a new measurement named 'LabC_S11'
            self.writeAndLog("DISP:WIND:TRAC%d:FEED '%s'" % (1, newName))  # Display the trace of new measurement on front panel.
        elif quant.name in (
            'S21 - Enabled', 
            'S12 - Enabled', 
            'S22 - Enabled',
        ):
            param = quant.name[:3]
            self.getActiveMeasurements()
            # Clear all measurements.
            if param in self.dMeasParam:  # TODO: Strange condition.
                for name in self.dMeasParam[param]:
                    self.writeAndLog("CALC:PAR:DEL '%s'" % name)
            # Add a new measurement if enabled.
            if value is True:
                newName = 'LabC_%s' % param
                self.writeAndLog("CALC:PAR:DEF '%s',%s" % (newName, param))  # Add a new measurement.
                iTrace = 1 + ['S11', 'S21', 'S12', 'S22'].index(param)
                # Add a new trace for displaying measurement
                self.writeAndLog("DISP:WIND:TRAC%d:FEED '%s'" % (iTrace, newName))
                self.dMeasParam[param] = [newName]  # Update list of currently active measurments.
        elif quant.name in (
            'Wait for new trace',
            # 'Range type', # TODO: Why?
        ):
            # Do nothing, just changing local values.
            pass
        else:
            # For all other cases, call VISA driver
            value = VISA_Driver.performSetValue(self, quant, value, sweepRate, options)
            # Try to get the value from instrument.
            if quant.get_cmd:
                value = self.askAndLog(quant.get_cmd)
            elif quant.set_cmd:
                value = self.askAndLog(quant.set_cmd+'?')
            else:
                pass
        return value


    def performGetValue(self, quant, options={}):
        """Perform the Get Value instrument operation"""
        if quant.name in (
            'S11 - Enabled', 
            'S21 - Enabled', 
            'S12 - Enabled',
            'S22 - Enabled',
        ):
            # Update list of currently active measurments.
            self.getActiveMeasurements()
            param = quant.name[:3]
            value = (param in self.dMeasParam)  # Return the actual value from instrument.
        elif quant.name in (
            'S11', 
            'S21', 
            'S12', 
            'S22', 
            'S11 - single point', 
            'S21 - single point', 
            'S12 - single point', 
            'S22 - single point',
        ):
            # Update list of currently active measurments.
            if quant.name not in self.dMeasParam:
                self.getActiveMeasurements()
            # Try to get the data from the measurement.
            if quant.name[:3] in self.dMeasParam:
                sName = self.dMeasParam[quant.name[:3]][-1]
                self.writeAndLog("CALC:PAR:SEL '%s'" % sName)  # Select a measurement.
                # 大多数CALC:命令都要求先选择测量，再改变设置。同一时刻每个通道可选择一个测量。

                bWaitTrace, bAverage, bStopped = self.measure_and_wait_done()
                # if stopped, don't return data
                if bWaitTrace and bStopped:  # TODO: Strange condition.
                    self.writeAndLog('*CLS;:INIT:CONT ON;')  # Clear and set continuous running.
                    return []

                vComplex = self.get_trace_data()
                if bWaitTrace and not bAverage:
                    self.writeAndLog(':INIT:CONT ON;')  # Set continuous running.
                if quant.name.endswith(' - single point'):
                    value = vComplex[0]
                else:
                    startFreq = self.readValueFromOther('Start frequency')
                    stopFreq = self.readValueFromOther('Stop frequency')
                    sweepType = self.readValueFromOther('Sweep type')
                    value = quant.getTraceDict(
                        vComplex, x0=startFreq, x1=stopFreq, logX=(sweepType == 'LOG')
                    )
            else:  # If no such measurement, i.e. not enabled.
                if quant.name.endswith(' - single point'):
                    value = 0
                else:
                    value = quant.getTraceDict([])
        elif quant.name in ('Wait for new trace',):
            # do nothing, return local value
            value = quant.getValue()
        else:
            # for all other cases, call VISA driver
            value = VISA_Driver.performGetValue(self, quant, options)
        return value

    def measure_and_wait_done(self):
        """Let instrument collect data and block the program until measurement is done.
        
        Returns: bWaitTrace, bAverage, bStopped.

        Note:
            Continious running will be turned off!
        """
        bWaitTrace = self.getValue('Wait for new trace')
        bAverage = self.getValue('Average')
        if bWaitTrace:
            # Clear averaging state.
            if bAverage:
                nAverage = self.getValue('# of averages')
                self.writeAndLog(':SENS:AVER:CLE;:ABOR;')  # Clear and restart average.
            else:
                self.writeAndLog(':ABOR;:INIT:CONT OFF;:INIT:IMM;*OPC')  # Stop average refresh a trace.

            self.wait(0.03)  # wait some time before first check
            bDone = False
            while (not bDone) and (not self.isStopped()):
                if bAverage:
                    sAverage = self.askAndLog('SENS:AVER:COUN?')  # Get average count.
                    bDone = (int(sAverage) >= nAverage)
                else:
                    stb = int(self.askAndLog('*ESR?'))  # Check error.
                    bDone = (stb & 1) > 0
                if not bDone:
                    self.wait(0.1)
                    continue
        else:
            pass
        return bWaitTrace, bAverage, self.isStopped()

    def get_trace_data(self):
        """Read trace data from instrument."""
        # Get data from instrument, in byte-string.
        self.writeAndLog(':FORM REAL,32')  # The default option is ASCii,0, which is very slow.
        self.write('CALC:DATA? SDATA', bCheckError=False)
        sData = self.read(ignore_termination=True)  # string of data in bytes.
        # sData += self.read(ignore_termination=True)  # FAILS! Try to access the remaining data.
        # Resolve float data from the byte-string.
        i0 = sData.find(b'#')
        nDig = int(sData[i0+1:i0+2])
        nByte = int(sData[i0+2:i0+2+nDig])
        nData = int(nByte/8)
        nPts = int(nData/2)
        # TODO: Raise error if there are too many data points, e.g. >1k.
        # Because the sData VISA.read returns string with at most 20480 long.
        # The reason why Keysight NA driver does not encounter this is because
        # the instrument returns VI_SUCCESS_MAX_CNT at VISA.read, in which case
        # VISA will automatically try second read for the ramaining data. 
        # while this instrument reutrns VI_SUCCESS as normal.
        vData = np.frombuffer(  # array([I1, Q1, I2, Q2, ...])
            sData[(i0+2+nDig):(i0+2+nDig+nByte)],
            dtype='d',  # np.dtype('float64')
            count=nData,
        )
        # Reshape array of real numbers into array of complex numbers.
        mC = vData.reshape((nPts,2))
        vComplex = mC[:,0] + 1j*mC[:,1]  # array([S12, s21'...], dtype=complex)
        return vComplex

    def getActiveMeasurements(self):
        """Get measurement-added-by-this-driver on instrument, and update self.dMeasParam.
        
        Updates self.dMeasParam like {'S21': ['LabR_S21', 'LabC_S21']}.
        """
        sAll = self.askAndLog('CALC:PAR:CAT?')  # 'CH1_WIN1_LINE1_PARAM1,S11,LabC_S21,S21'
        sAll = sAll[0:]  # 移除收尾字符

        self.dMeasParam = {}
        lAll = sAll.split(',')  # [CH1_WIN1_LINE1_PARAM1, S11, LabC_S21, S21]
        nMeas = len(lAll)//2
        for n in range(nMeas):
            sName = lAll[2*n]
            sParam = lAll[2*n + 1]
            if 'LabC' in sName:
                if sParam in self.dMeasParam:
                    self.dMeasParam[sParam].append(sName)
                else:
                    self.dMeasParam[sParam] = [sName,]
            else:
                pass



if __name__ == '__main__':
    pass
