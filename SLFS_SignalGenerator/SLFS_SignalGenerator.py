#!/usr/bin/env python
"""
@author: Ji Chu
@author: Jiawei Qiu
"""
from VISA_Driver import VISA_Driver

__version__ = "0.3"

class Error(Exception):
    pass

class Driver(VISA_Driver):
    """ This class implements the ...... driver"""

    def performOpen(self, options={}):
        """Perform the operation of opening the instrument connection"""
        # calling the generic VISA open to make sure we have a connection
        VISA_Driver.performOpen(self, options=options)

    def performSetValue(self, quant, value, sweepRate=0.0, options={}):
        """Perform the Set Value instrument operation. This function should
        return the actual value set by the instrument"""
        # NOTICE: This instr always replys to cmd, so a read action should follow every write action, use askAndLog fot this.
        if quant.name in ('Output'):
            # Use LEVEL:STATE ON/OFF to set the value, but not LEVEL:STATE 0/1.
            if value:  # BUG: Seems Labber instrument server and measurement editor pass different value. One is True/False, the other is 0/1.
                res = self.askAndLog('LEVEL:STATE ON')
            else:
                res = self.askAndLog('LEVEL:STATE OFF')
            # raise Exception(f'res: {res}\nvalue: {value}')
        elif quant.name in ('Level', 'Frequency'):
            # Use askAndLog to insure each write action is followed by a read.
            s_value = quant.getCmdStringFromValue(value)
            cmd = quant.set_cmd.replace('<*>', s_value)
            res = self.askAndLog(cmd)
        elif quant.name[0:3] == 'REF':
            # Use REF_XXX:STATE INT/EXT to set the value, but not REF_XXX:STATE 0/1.
            res = self.askAndLog(quant.set_cmd + ' ' + value)
        else:
            value = VISA_Driver.performSetValue(self, quant, value, sweepRate, options)
        return value


    def performGetValue(self, quant, options={}):
        """Perform the Get Value instrument operation"""
        if quant.name in ('Frequency'):
            value = VISA_Driver.performGetValue(self, quant, options) / 1e2  # Return value is pad with 0 in the end.
        elif quant.name in ('Level', 'Output', 'REF_10M', 'REF_1.6G'):
            value = VISA_Driver.performGetValue(self, quant, options)  # value will be converted according to combo_defs, if there exists.
        else:
            value = quant.getValue()

        return value


if __name__ == '__main__':
    pass
