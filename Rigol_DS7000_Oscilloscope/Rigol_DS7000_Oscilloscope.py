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
        # check type of quantity
        if quant.name in ('Ch1 - Data', 'Ch2 - Data', 'Ch3 - Data', 'Ch4 - Data'):
            # traces, get channel
            channel = int(quant.name[2])
            # check if channel is on
            if self.getValue('Ch%d - Enabled' % channel):
                self.writeAndLog(':WAV:SOUR CHAN%d' % channel)
                self.writeAndLog(':WAV:MODE NORMal')
                self.writeAndLog(':WAV:FORM ASCii')

                raw_data = self.askAndLog(':WAV:DATA?')
                string_list=raw_data[11:-1].split(',')         
                # 9000014000XXXXXXX
                wave_list=[float(s) for s in string_list]
                self.log(len(wave_list))


                origin_point = float(self.askAndLog(':WAVeform:XORigin?'))
                x_incre=float(self.askAndLog(':WAVeform:XINCrement?'))


                value = InstrumentQuantity.getTraceDict(wave_list, x0=origin_point  ,dx=x_incre  )

            else:
                # not enabled, return empty array
                value = np.asarray([])
        else:
            # for all other cases, call VISA driver
            value = VISA_Driver.performGetValue(self, quant, options)
        return value

if __name__ == '__main__':
    pass


