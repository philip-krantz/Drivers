"""
@author: Jiahao Yuan
"""
from VISA_Driver import VISA_Driver
import numpy as np
import time

__version__ = "0.1"

class Error(Exception):
    pass

class Driver(VISA_Driver):
    """ This class implements the Rigol Arbitrary Waveform Generator driver"""

    def performOpen(self, options={}):
        """Perform the operation of opening the instrument connection"""
        # calling the generic VISA open to make sure we have a connection
        VISA_Driver.performOpen(self, options=options)
        # check if in DC mode
        for n in range(2):
            ch = n+1
            wfInfor = self.askAndLog(f'SOUR{ch}:APPL?')
            if wfInfor.strip('"').split(',')[0] != 'DC':
                self.writeAndLog(f':SOUR{ch}:APPL:DC 1,1,0')

    def performSetValue(self, quant, value, sweepRate=0.0, options={}):
        """Perform the Set Value instrument operation. This function should
        return the actual value set by the instrument"""
        if quant.name in ('Ch1 - voltage', 'Ch2 - voltage'):
            ch = quant.name[2]
            start = self.readValueFromOther(quant.name)
            stop = value
            self.log(f'Set {quant.name} called. start:{start}, stop:{stop}')
            dt = 0.1
            rate = self.getValue('Sweep speed')
            step = min(rate*dt, abs(stop-start)/2)*np.sign(stop-start)
            value = start
            while np.sign((value-stop)*(start-stop))==1 and not self.isStopped():
                if np.sign((value+step-stop)*(start-stop))==1:
                    value = value+step
                else:
                    value = stop
                self.writeAndLog(f':SOUR{ch}:APPL:DC 1,1,{value}')
                time.sleep(dt)
        elif quant.name in ('Sweep speed'):
            quant.setValue(value)
        else:
            value = VISA_Driver.performSetValue(self, quant, value, sweepRate, options)
        # wait for instrument
        time.sleep(0.05)
        return value

    def performGetValue(self, quant, options={}):
        """Perform the Get Value instrument operation"""
        # check type of quantity
        if quant.name in ('Ch1 - voltage', 'Ch2 - voltage'):
            ch = quant.name[2]
            wfInfor = self.askAndLog(f'SOUR{ch}:APPL?')
            # returned message is like "DC,DEF,DEF,1.000000E+00"
            value = float(wfInfor.strip('"').split(',')[-1])
        elif quant.name in ('Sweep speed'):
            value = quant.getValue()
        else:
            # for all other cases, call VISA driver
            value = VISA_Driver.performGetValue(self, quant, options)
        return value

    def performClose(self, bError=False, options={}):
        """Perform the close instrument connection operation"""
        # calling the generic VISA class to close communication
        self.writeAndLog('OUTPUT1 OFF;OUTPUT2 OFF')
        VISA_Driver.performClose(self, bError, options=options)
