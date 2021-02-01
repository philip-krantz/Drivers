#!/usr/bin/env python

import InstrumentDriver
from VISA_Driver import VISA_Driver
import numpy as np
import re

__version__ = '1.3.0'

MIN_WAVE_LENGTH = 2400
channel_re = re.compile(r'Ch (\d)$')
marker_re = re.compile(r'Ch (\d) - Marker (\d)$')
class Driver(VISA_Driver):
    """ This class implements the Tektronix AWG5200 series driver"""

    def performOpen(self, options={}):
        """Perform the operation of opening the instrument connection"""
        # start by calling the generic VISA open to make sure we have a connection
        VISA_Driver.performOpen(self, options)
        # get model name and number of channels
        sModel = self.getModel()
        if sModel == '5208':
            self.nCh = 8
        elif sModel == '5204':
            self.nCh = 4
        elif sModel == '5202':
            self.nCh = 2
        self.nMarker = 4
        self.initSetConfig()

    def performClose(self, bError=False, options={}):
        """Perform the close instrument connection operation"""
        # close VISA connection
        VISA_Driver.performClose(self, bError, options)


    def initSetConfig(self):
        """This function is run before setting values in Set Config"""
        # turn off run mode
        self.bIsStopped = False
        self.awg_stop()
        # init vectors with old values
        self.bWaveUpdated = False
        self.nOldSeq = -1
        # waveform use single precision float
        self.lOldReal = [[np.array([], dtype='f4') \
                       for n1 in range(self.nCh)] for n2 in range(1)]
        # marker use single byte. four most significant bits are used.
        # bit 7 for marker 1, bit 6 for marker 2, ...
        self.lOldMark = [[np.array([], dtype='u1') \
                       for n1 in range(self.nCh)] for n2 in range(1)]
        # clear old waveforms
        self.writeAndLog(':WLIS:WAV:DEL ALL')
        self.lInUse = [False]*self.nCh
        for n in range(self.nCh):
            channel = n+1
            self.setValue(f'Ch {channel}', [])
            for m in range(self.nMarker):
                self.setValue(f'Ch {channel} - Marker {m+1}', [])
            self.createWaveformOnTek(channel, 0, bOnlyClear=True)


    def performSetValue(self, quant, value, sweepRate=0.0, options={}):
        """Perform the Set Value instrument operation. This function should
        return the actual value set by the instrument"""
        # keep track of if waveform is updated, to avoid sending it many times
        if self.isFirstCall(options):
            self.bWaveUpdated = False
            # if sequence mode, make sure the buffer contains enough waveforms
            if self.isHardwareLoop(options):
                (seq_no, n_seq) = self.getHardwareLoopIndex(options)
                # if first call, clear sequence and create buffer
                if seq_no==0:
                    # variable for keepin track of sequence updating
                    self.awg_stop()
                    self.bSeqUpdate = False
                # if different sequence length, re-create buffer
                if seq_no==0 and n_seq != len(self.lOldReal):
                    self.lOldReal = [[np.array([], dtype='f4') \
                        for n1 in range(self.nCh)] for n2 in range(n_seq)]
                    self.lOldMark = [[np.array([], dtype='u1') \
                        for n1 in range(self.nCh)] for n2 in range(n_seq)]
            elif self.isHardwareTrig(options):
                # if hardware triggered, always stop outputting before setting
                self.awg_stop()
        if channel_re.match(quant.name) or marker_re.match(quant.name):
            # set value, then mark that waveform needs an update
            quant.setValue(value)
            self.bWaveUpdated = True
        elif quant.name in ('Sequence - Trigger source'):
            quant.setValue(value)
        elif quant.name in ('Run'):
            if value:
                self.awg_run(force=True)
                # turn on channels again, to avoid issues when switch run mode
                # self.turn_on_in_use()
            else:
                # stop AWG
                self.awg_stop(force=True)
        elif quant.name in ('Stop'):
            self.awg_stop(force=True)
        else:
            if quant.name in ('Sample rate'):
                inst_options = self.getOptions()
                if '2.5GS/s Sample Rate' in inst_options:
                    max_sample_rate = 2.5E9
                elif '5GS/s Sample Rate' in inst_options:
                    max_sample_rate = 5E9
                if max_sample_rate and value > max_sample_rate:
                    value = max_sample_rate
            # for all other cases, call VISA driver
            value = VISA_Driver.performSetValue(self, quant, value, sweepRate,
                                                options=options)
        # if final call and wave is updated, send it to AWG
        if self.isFinalCall(options) and self.bWaveUpdated:
            (seq_no, n_seq) = self.getHardwareLoopIndex(options)
            if self.isHardwareLoop(options):
                seq = seq_no
                self.reportStatus('Sending waveform (%d/%d)' % (seq_no+1, n_seq))
            else:
                seq = None

            # in trig mode, don't start AWG if trig channel will start it later
            if ((self.isHardwareTrig(options) and
                 self.getTrigChannel(options) == 'Run')):
                bStart = False
            else:
                bStart = True
            self.sendWaveformAndStartTek(seq=seq, n_seq=n_seq, bStart=bStart)
        return value


    def performGetValue(self, quant, options={}):
        """Perform the Get Value instrument operation"""
        # check type of quantity
        if channel_re.match(quant.name) or marker_re.match(quant.name) or \
            quant.name in ('Sequence - Trigger source'):
            # do nothing here
            value = quant.getValue()
        else:
            # for all other cases, call VISA driver
            value = VISA_Driver.performGetValue(self, quant, options)
        return value


    def sendWaveformAndStartTek(self, seq=None, n_seq=1, bStart=True):
        """Rescale and send waveform data to the Tek"""
        self.nPrevData = 0
        self.bIsStopped = False
        # go through all channels
        for n in range(self.nCh):
            # channels are numbered 1-8
            channel = n+1
            vData = self.getValueArray(f'Ch {channel}')
            vMark = []
            for m in range(self.nMarker):
                vMark.append(self.getValueArray(f'Ch {channel} - Marker {m+1}'))
            bWaveUpdate = self.sendWaveformToTek(channel, vData, vMark, seq)
        # check if sequence mode
        if seq is not None:
            # if not final seq call, just return here
            self.bSeqUpdate = self.bSeqUpdate or bWaveUpdate
            if (seq+1) < n_seq:
                return
            filename = 'Labber_SEQ'
            # final call, check if sequence has changed
            if self.bSeqUpdate or n_seq != self.nOldSeq:
                # create sequence list
                self.writeAndLog(f':SLIS:SEQ:DEL "{filename}"')
                self.writeAndLog(f':SLIS:SEQ:NEW "{filename}",{n_seq}')
                for n1 in range(n_seq):
                    for n2, bUpdate in enumerate(self.lInUse):
                        if bUpdate:
                            name = f'Labber_{n2+1}_{n1+1}'
                            self.writeAndLog(
                                f':SLIS:SEQ:STEP{n1+1}:TASS{n2+1}'
                                f':WAV "{filename}","{name}"')
                    # always wait for trigger
                    trig = self.getValue('Sequence - Trigger source')
                    if trig == 'Internal':
                        trig = 'ITR'
                    elif trig == 'A':
                        trig = 'ATR'
                    else:
                        trig = 'BTR'
                    self.writeAndLog(
                        f':SLIS:SEQ:STEP{n1+1}:WINP "{filename}",{trig}')
                # for last element, set jump to first
                self.writeAndLog(f':SLIS:SEQ:STEP{n_seq}:GOTO "{filename}",FIRS')
                # save old sequence length
                self.nOldSeq = n_seq
            # turn on channels in use 
            self.turn_on_in_use(seq=True)
            return
        # turn on channels in use 
        self.turn_on_in_use()
        # if not starting, make sure AWG is not running, then return
        if not bStart:
            self.awg_stop()
            return
        # send command to turn on run mode to tek
        self.awg_run()
        # turn on channels again, to avoid issues when turning on/off run mode
        # self.turn_on_in_use()


    def scaleWaveformToReal(self, vData, dVpp, ch):
        """Scales the waveform and returns data in a string of Real"""
        # make sure waveform data is within the voltage range 
        if np.any(vData > dVpp/2) or np.any(vData < -dVpp/2):
            raise InstrumentDriver.Error(
                f'Waveform for channel {ch} contains values that are '
                f'outside the channel voltage range.')
        # clip waveform and store in-place
        np.clip(vData, -dVpp/2., dVpp/2., vData)
        # -1. to 1. float
        vReal = np.array(vData*2/dVpp, dtype='f4')
        return vReal


    def createWaveformOnTek(self, channel, length, seq=None, bOnlyClear=False):
        """Remove old and create new waveform on the Tek. The waveform is named
        by the channel number"""
        if seq is None:
            name = 'Labber_%d' % channel
        else:
            name = 'Labber_%d_%d' % (channel, seq+1)
        # first, turn off output
        self.sendValueToOther(f'Ch{channel} - Output', False)
        if bOnlyClear:
            # just clear this channel
            self.writeAndLog(':SOUR%d:CASS:CLE;' % channel)
        else:
            # remove old waveform, ignoring errors, then create new
            self.writeAndLog(':WLIS:WAV:DEL "%s"; *CLS' % name, bCheckError=False)
            self.writeAndLog(':WLIS:WAV:NEW "%s",%d,REAL;' % (name, length))
    

    def sendWaveformToTek(self, channel, vData, vMark, seq=None):
        """Send waveform to Tek"""
        # check if sequence. iSeq is used for index
        if seq is None:
            iSeq = 0
        else:
            iSeq = seq
        # channels are named 1-8
        n = channel-1
        # length of markers
        mark_len = np.fromiter(map(len, vMark), 'i')
        if len(vData)==0:
            nMark = max(mark_len)
            if nMark==0:
                # if channel in use, turn off, clear, go to next channel
                if self.lInUse[n]:
                    self.createWaveformOnTek(channel, 0, seq, bOnlyClear=True)
                    self.lOldReal[iSeq][n] = np.array([], dtype='f4')
                    self.lOldMark[iSeq][n] = np.array([], dtype='u1')
                    self.lInUse[n] = False
                return False
            else:
                # no data, but markers exist, output zeros for data
                vData = np.zeros((nMark,), dtype='f4')
        # make sure length of data is the same
        if (np.any(np.logical_and(mark_len>0, mark_len!=len(vData)))) or \
           (self.nPrevData>0 and self.nPrevData!=len(vData)):
            raise InstrumentDriver.Error(\
                  'All channels need to have the same number of elements')
        self.nPrevData = len(vData)
        if len(vData) < MIN_WAVE_LENGTH:
            self.log(
                f'Seq:{seq} Waveform length is shorter than minimum value. '
                f'Padding to {MIN_WAVE_LENGTH} points with edge value.')
            vData = np.pad(vData, (0,MIN_WAVE_LENGTH-len(vData)), mode='edge')
            for m, marker in enumerate(vMark):
                if len(marker)!=0:
                    vMark[m] = np.pad(marker, (0,MIN_WAVE_LENGTH-len(marker)),
                        mode='edge')
        # channel in use, mark
        self.lInUse[n] = True
        # get range and scale to Real
        Vpp = self.getValue('Ch%d - Range' % channel)
        vReal = self.scaleWaveformToReal(vData, Vpp, channel)
        # check for marker traces
        vMarkByte = np.zeros((len(vReal),), dtype='u1')
        for m, marker in enumerate(vMark):
            if len(marker)==len(vReal):
                # get marker trace
                vMarkBit = np.array(marker != 0, dtype='u1')
                # add marker trace to data trace, with bit shift
                # Bit 7 stores marker 1, Bit 6 stores marker 2, ...
                vMarkByte += vMarkBit << (7-m)
        # send waveform data
        Rstart, Rlength = 0, len(vReal)
        Mstart, Mlength = 0, len(vReal)
        # compare to previous trace
        if Rlength != len(self.lOldReal[iSeq][n]):
            # stop AWG if still running
            self.awg_stop()
            # len has changed, del old waveform and create new
            self.createWaveformOnTek(channel, Rlength, seq)
        else:
            # same length, check for similarities
            vRIndx = np.nonzero(vReal != self.lOldReal[iSeq][n])[0]
            vMIndx = np.nonzero(vMarkByte != self.lOldMark[iSeq][n])[0]
            if (len(vRIndx) == 0) and (len(vMIndx) == 0):
                # nothing changed, don't update, go on to next
                return False
            # some elements changed, find start and length
            if len(vRIndx) != 0:
                Rstart = vRIndx[0]
                Rlength = vRIndx[-1] - vRIndx[0] + 1
            else:
                Rlength = 0
            if len(vMIndx) != 0:
                Mstart = vMIndx[0]
                Mlength = vMIndx[-1] - vMIndx[0] + 1
            else:
                Mlength = 0
        # stop AWG if still running
        self.awg_stop()
        # send to tek, start by turning off output
        self.sendValueToOther(f'Ch{channel} - Output', False)
        if seq is None:
            # non-sequence mode, get name
            name = b'Labber_%d' % channel
            # (re-)set waveform to channel
            self.writeAndLog(':SOUR%d:CASS:WAV "%s"' % (channel, name.decode()))
        else:
            # sequence mode, get name
            name = b'Labber_%d_%d' % (channel, seq+1)
        if Rlength > 0:
            sSend = b':WLIS:WAV:DATA "%s",%d,%d,' % (name, Rstart, Rlength)
            self.write_binary(sSend, vReal[Rstart:Rstart+Rlength])
            # store new waveform for next call
            self.lOldReal[iSeq][n] = vReal
        if Mlength > 0:
            sSend = b':WLIS:WAV:MARK:DATA "%s",%d,%d,' % (name, Mstart, Mlength)
            self.write_binary(sSend, vMarkByte[Mstart:Mstart+Mlength])
            self.lOldMark[iSeq][n] = vMarkByte
        return True


    def awg_stop(self, force=False):
        if self.bIsStopped and not force:
            return
        self.bIsStopped = True
        self.writeAndLog(':AWGC:STOP;')
        # wait for output to be turned off
        iRunState = int(self.askAndLog(':AWGC:RST?'))
        nTry = 1000
        while nTry>0 and iRunState!=0 and not self.isStopped():
            # sleep for while to save resources, then try again
            self.wait(0.05)
            # try again
            iRunState = int(self.askAndLog(':AWGC:RST?'))
            nTry -= 1
        # check if timeout occurred
        if nTry <= 0:
            # timeout
            raise InstrumentDriver.Error('Cannot turn off Run mode')
    

    def awg_run(self, force=False):
        if not self.bIsStopped and not force:
            return
        self.bIsStopped = False
        self.writeAndLog(':AWGC:RUN;')
        # wait for output to be turned on
        iRunState = int(self.askAndLog(':AWGC:RST?'))
        nTry = 1000
        while nTry>0 and iRunState==0 and not self.isStopped():
            # sleep for while to save resources, then try again
            self.wait(0.05)
            # try again
            iRunState = int(self.askAndLog(':AWGC:RST?'))
            nTry -= 1
        # check if timeout occurred
        if nTry <= 0:
            # timeout
            raise InstrumentDriver.Error('Cannot turn on Run mode')
    
    
    def turn_on_in_use(self, seq=None):
        """Turn on output of channels in use"""
        for n, bUpdate in enumerate(self.lInUse):
            if bUpdate:
                self.sendValueToOther(f'Ch{n+1} - Output', True)
                if seq is not None:
                    self.writeAndLog(f':SOUR{n+1}:CASS:SEQ "Labber_SEQ",{n+1}')

    def write_binary(self, sCmd, data):
        """Write binary data, no log"""
        # create binary data as bytes with header
        sLen = b'%d' % (data.dtype.itemsize*len(data))
        sHead = b'#%d%s' % (len(sLen), sLen)
        sSend = b'%s%s' % (sCmd, sHead + data.tobytes())
        self.write_raw(sSend)

    
if __name__ == '__main__':
    pass
