#!/usr/bin/env python
"""
@author: Ji Chu
"""
from VISA_Driver import VISA_Driver
from InstrumentConfig import InstrumentQuantity
import numpy as np

__version__ = "0.0.1"


class Driver(VISA_Driver):
    """ This class implements the Rigol scope driver"""

    def performGetValue(self, quant, options={}):
        """Perform the Get Value instrument operation"""

        if quant.name in ('Ch1 - Data', 'Ch2 - Data', 'Ch3 - Data', 'Ch4 - Data'):
            # traces, get channel
            channel = int(quant.name[2])
            # check if channel is on
            if self.getValue('Ch%d - Enabled' % channel):
                self.writeAndLog('FORMAT:DATA ASCii')
                raw_data = self.askAndLog('CHAN%d:WAV:DATA:VAL?'%channel)
                string_list=raw_data.split(',')         
                data_list=[float(s) for s in string_list]
                self.log(len(data_list))

                if self.getValue('Return X value'):
                    x_list=data_list[0::2]
                    y_list=data_list[1::2]
                    value = InstrumentQuantity.getTraceDict(y_list, x=x_list  )
                else:
                    y_list = data_list
                    x_incre = float(self.askAndLog('TIMebase:RANGe?'))/len(y_list)
                    value = InstrumentQuantity.getTraceDict(y_list, x0=0 ,dx=x_incre)

            else:
                # not enabled, return empty array
                value = np.asarray([])
        else:
            # for all other cases, call VISA driver
            value = VISA_Driver.performGetValue(self, quant, options)
        return value

if __name__ == '__main__':
    pass


