import sys
from pathlib import Path

sys.path.append(str(Path('../Helper_Lib').resolve()))

from driver_config import (
    LDriverDefinition, LDouble, LCombo, LVector, LButton, LBoolean
)

if __name__ == "__main__":
    dir_path = Path(__file__).parent
    f = LDriverDefinition(dir_path/'Tektronix_AWG5200.ini')
    f.add_general_settings(
        name='Tektronix AWG5200',
        version='1.3.0',
        driver_path='Tektronix_AWG5200',
        interface='TCPIP',
        support_arm=False,
        support_hardware_loop=True,
    )
    model_5208 = (5208, 'TEKTRONIX,AWG5208')
    model_5204 = (5204, 'TEKTRONIX,AWG5204')
    model_5202 = (5202, 'TEKTRONIX,AWG5202')
    models = [
        model_5208,
        model_5204,
        model_5202,
    ]
    options = [
        ('2.5GS/s Sample Rate', 25),
        ('5GS/s Sample Rate', 50),
        ('Sequencing', 'SEQ'),
    ]
    f.add_models_and_options(
        models=models,
        check_model=True,
        check_options=True,
        option_cmd='*OPT?',
        options=options,
    )
    f.add_VISA_settings(
        use_visa=True,
        reset=True,
        timeout=60,
        query_instr_errors=False,
        error_bit_mask=255,
        error_cmd=':SYST:ERR?',
    )





    # Clock setting
    #region Section: Clock
    f.add_section('Clock')
    f.add_group(None)

    ref_int = ('Internal', 'INT')
    ref_ext10 = ('Reference In, External 10MHz', 'EFIX')
    ref_extv = ('Reference In, External Variable', 'EVAR')
    ref_clk = ('Clock In, External Variable', 'EXT')
    combo_ref = LCombo(
        'Reference',
        def_value=ref_int,
        combo=[
            ref_int,
            ref_ext10,
            ref_extv,
            ref_clk,
        ],
        set_cmd='CLOC:SOUR'
    )
    f.add_quantity(combo_ref)

    f.add_quantity(LDouble(
        'Ext. clock frequency',
        unit='Hz',
        def_value=2.5e9,
        low_lim=2.5e9,
        high_lim=5e9,
        set_cmd='CLOC:ECL:FREQ',
        state_quant=combo_ref,
        states=[ref_clk],
    ))

    f.add_quantity(LDouble(
        'Ext. reference frequency',
        unit='Hz',
        def_value=35e6,
        low_lim=35e6,
        high_lim=250e6,
        set_cmd='CLOC:EREF:FREQ',
        state_quant=combo_ref,
        states=[ref_extv],
    ))

    f.add_quantity(LBoolean(
        'Jitter reduction',
        def_value=False,
        set_cmd='CLOC:JITT',
        state_quant=combo_ref,
        states=[
            ref_int,
            ref_ext10,
            ref_extv
        ],
    ))

    f.add_quantity(LBoolean(
        'Clock out',
        def_value=False,
        set_cmd='CLOC:OUTP',
        state_quant=combo_ref,
        states=[
            ref_int,
            ref_ext10,
            ref_extv
        ],
    ))

    f.add_quantity(LDouble(
        'Sample rate',
        unit='Hz',
        def_value=2.5e9,
        low_lim=298,
        set_cmd='CLOC:SRAT',
        state_quant=combo_ref,
        states=[
            ref_int,
            ref_ext10,
            ref_extv
        ],
        show_in_measurement_dlg=True,
    ))
    #endregion Section: Clock





    # Trigger settings
    #region Section: Trigger
    f.add_section('Trigger')
    f.add_group('Internal trigger')

    f.add_quantity(LDouble(
        'Internal Trigger - interval',
        label='interval',
        unit='s',
        def_value=1e-3,
        low_lim=1e-6,
        high_lim=10,
        set_cmd='TRIG:INT',
        show_in_measurement_dlg=True,
    ))

    for source in ['A', 'B']:
        f.add_group(f'External trigger input {source}')

        f.add_quantity(LDouble(
            f'Trigger {source} - level',
            label='level',
            unit='V',
            def_value=1.4,
            low_lim=-5,
            high_lim=5,
            set_cmd=f'TRIG:LEV <*>,{source}TR',
            get_cmd=f'TRIG:LEV? {source}TR',
        ))

        slope_pos = ('Positive', 'POS')
        slope_neg = ('Negative', 'NEG')
        combo_slope = LCombo(
            f'Trigger {source} - slope',
            label='slope',
            def_value=slope_pos,
            combo=[
                slope_pos,
                slope_neg,
            ],
            set_cmd=f'TRIG:SLOP <*>,{source}TR',
            get_cmd=f'TRIG:SLOP? {source}TR',
        )
        f.add_quantity(combo_slope)

        imp_50 = ('50 Ohm', 50)
        imp_1k = ('1 kOhm', 1000)
        combo_imp = LCombo(
            f'Trigger {source} - impedance',
            label='impedance',
            def_value=imp_50,
            combo=[
                imp_50,
                imp_1k,
            ],
            set_cmd=f'TRIG:IMP <*>,{source}TR',
            get_cmd=f'TRIG:IMP? {source}TR',
        )
        f.add_quantity(combo_imp)

        f.add_quantity(LButton(
            f'Trigger {source} - Send Trig',
            label='Send Trig',
            set_cmd=f'TRIG {source}TR',
        ))
    #endregion Section: Trigger





    # AWG control
    f.add_section('Control')
    f.add_group(None)
    f.add_quantity(LButton(
        'Run',
        tooltip='Set instrument to run mode'
    ))

    f.add_quantity(LButton(
        'Stop',
        tooltip='Set instrument to stop mode'
    ))

    f.add_quantity(LBoolean(
        'All output off',
        def_value=False,
        set_cmd='OUTP:OFF'
    ))





    # Sequence trigger
    f.add_section('Sequence')
    f.add_group(None)
    trig_int = ('Internal', 'ITR')
    trig_A = ('A', 'ATR')
    trig_B = ('B', 'BTR')
    combo_seq_trig = LCombo(
        'Sequence - Trigger source',
        label='Trigger Source',
        def_value=trig_int,
        combo=[
            trig_int,
            trig_A,
            trig_B,
        ]
    )
    f.add_quantity(combo_seq_trig)





    # Channel settings
    #region Section: Channel
    for i in range(8):
        channel = i+1
        if 2 < channel <= 4:
            model_ch = [
                model_5204,
                model_5208
            ]
        elif channel>4:
            model_ch = [model_5208]
        else:
            model_ch = None
        f.add_section(f'Channel {channel}')
        f.add_group('Channel')

        f.add_quantity(LBoolean(
            f'Ch{channel} - Output',
            label='Output',
            def_value=False,
            set_cmd=f'OUTP{channel}',
            models=model_ch,
        ))

        mode_cont = ('Continuous', 'CONT')
        mode_trig = ('Triggered', 'TRIG')
        mode_tcon = ('Triggered Continuous', 'TCON')
        mode_gat = ('Gated', 'GAT')
        combo_run_mode = LCombo(
            f'Ch{channel} - Run mode',
            label='Run mode',
            def_value=mode_trig,
            combo=[
                mode_cont,
                mode_trig,
                mode_tcon,
                mode_gat,
            ],
            set_cmd=f'SOUR{channel}:RMODE',
            models=model_ch,
        )
        f.add_quantity(combo_run_mode)

        combo_ch_trig = LCombo(
            f'Ch{channel} - Trigger Source',
            label='Trigger Source',
            def_value=trig_A,
            combo=[
                trig_A,
                trig_B,
                trig_int,
            ],
            set_cmd=f'SOUR{channel}:TINP',
            state_quant=combo_run_mode,
            states=[
                mode_trig,
                mode_tcon,
            ],
            models=model_ch,
        )
        f.add_quantity(combo_ch_trig)

        combo_ch_trig_gat = LCombo(
            f'Ch{channel} - Trigger Source Gated',
            label='Trigger Source',
            def_value=trig_A,
            combo=[
                trig_A,
                trig_B,
            ],
            set_cmd=f'SOUR{channel}:TINP',
            state_quant=combo_run_mode,
            states=[
                mode_gat,
            ],
            models=model_ch,
        )
        f.add_quantity(combo_ch_trig_gat)

        f.add_quantity(LDouble(
            f'Ch{channel} - Range',
            label='Range',
            def_value=0.5,
            low_lim=0.025,
            high_lim=0.75,
            unit='V',
            set_cmd=f'SOUR{channel}:VOLT',
            models=model_ch,
        ))
        
        f.add_quantity(LDouble(
            f'Ch{channel} - Offset',
            label='Offset',
            def_value=0,
            low_lim=-2,
            high_lim=2,
            unit='V',
            set_cmd=f':SOUR{channel}:VOLT:OFFS',
            models=model_ch,
        ))

        f.add_quantity(LDouble(
            f'Ch{channel} - Skew',
            label='Skew',
            tooltip='Minimum step is 0.5 ps',
            def_value=0,
            low_lim=-2e-9,
            high_lim=2e-9,
            unit='s',
            set_cmd=f'SOUR{channel}:SKEW',
            models=model_ch,
        ))

        dac_16 = ('16 bit DAC + 0 marker', 16)
        dac_15 = ('15 bit DAC + 1 marker', 15)
        dac_14 = ('14 bit DAC + 2 marker', 14)
        dac_13 = ('13 bit DAC + 3 marker', 13)
        dac_12 = ('12 bit DAC + 4 marker', 12)
        combo_dac = LCombo(
            f'Ch{channel} - DAC',
            label='DAC resolution',
            def_value=dac_16,
            combo=[
                dac_16,
                dac_15,
                dac_14,
                dac_13,
                dac_12,
            ],
            set_cmd=f'SOUR{channel}:DAC:RES',
            models=model_ch,
        )
        f.add_quantity(combo_dac)

        f.add_quantity(LVector(
            f'Ch {channel}',
            group='Output',
            permission='WRITE',
            unit='V',
            x_name='Time',
            x_unit='s',
            show_in_measurement_dlg=True,
            models=model_ch,
        ))
        # Marker settings
        #region Group: Marker
        for j in range(4):
            marker = j+1
            f.add_group(f'Marker {marker}')

            f.add_quantity(LDouble(
                f'Ch{channel} - Marker {marker} High',
                label=f'Marker {marker} High',
                def_value=1.0,
                low_lim=-0.3,
                high_lim=1.75,
                unit='V',
                set_cmd=f'SOUR{channel}:MARK{marker}:VOLT:HIGH',
                models=model_ch,
            ))
            
            f.add_quantity(LDouble(
                f'Ch{channel} - Marker {marker} Low',
                label=f'Marker {marker} Low',
                def_value=0,
                low_lim=-0.5,
                high_lim=1.55,
                unit='V',
                set_cmd=f'SOUR{channel}:MARK{marker}:VOLT:LOW',
                models=model_ch,
            ))

            f.add_quantity(LDouble(
                f'Ch{channel} - Marker {marker} Delay',
                label=f'Marker {marker} Delay',
                def_value=0,
                low_lim=-3e-9,
                high_lim=3e-9,
                unit='s',
                set_cmd=f'SOUR{channel}:MARK{marker}:DEL',
                models=model_ch,
            ))

            f.add_quantity(LVector(
                f'Ch {channel} - Marker {marker}',
                group='Output',
                permission='WRITE',
                unit='V',
                x_name='Time',
                x_unit='s',
                models=model_ch,
            ))
        #endregion Group: Marker
    #endregion Section: Channel