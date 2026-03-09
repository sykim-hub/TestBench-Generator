import os
import re


class TestbenchGenerator:
    def __init__(self, template_path):
        self.template_path = template_path
        with open(template_path, 'r', encoding='utf-8') as f:
            self.template = f.read()

    # ──────────────────────────────────────────────────────────────────────────
    # Public entry point
    # ──────────────────────────────────────────────────────────────────────────
    def generate(self, parsed_data, config):
        """
        parsed_data : Output from HDLParser.parse()
        config      : {
            'tb_name'       : str,
            'clocks'        : [{'name', 'frequency_mhz', 'duty_cycle', 'port'}, ...],
            'resets'        : [{'name', 'active_low', 'delay_ns', 'auto_reset', 'port'}, ...],
            'task_sequence' : [{'task_file', 'fork_type'}, ...],
            'library_tasks' : [filename, ...],   # unique files to include
        }
        """
        module_name = parsed_data.get('module_name', 'unknown_dut')
        tb_name     = config.get('tb_name', f'tb_{module_name}')

        clocks  = config.get('clocks',  [{'name': 'clk',   'frequency_mhz': 100.0, 'duty_cycle': 50.0, 'port': 'clk'}])
        resets  = config.get('resets',  [{'name': 'rst_n', 'active_low': True,    'delay_ns': 100.0,  'auto_reset': True, 'port': 'rst_n'}])

        # Exclusion set: DUT port names AND TB signal names that are handled
        # by clock/reset entries — prevents double `reg` declarations when the
        # user names a TB signal the same as an unrelated DUT input port.
        clk_rst_exclude = set()
        for c in clocks:
            clk_rst_exclude.add(c.get('port', c['name']))  # DUT port name
            clk_rst_exclude.add(c['name'])                  # TB signal name
        for r in resets:
            clk_rst_exclude.add(r.get('port', r['name']))  # DUT port name
            clk_rst_exclude.add(r['name'])                  # TB signal name

        # ── 1. Signal Declarations ───────────────────────────────────────────
        def fmt_signals(sig_list, sig_type):
            return '\n'.join(
                f"{sig_type}{(' ' + s['width']) if s.get('width') else ''} {s['name']};"
                for s in sig_list
            )

        general_inputs  = [s for s in parsed_data.get('inputs',  []) if s['name'] not in clk_rst_exclude]
        output_signals  = fmt_signals(parsed_data.get('outputs', []), 'wire')
        inout_signals   = fmt_signals(parsed_data.get('inouts',  []), 'wire')
        input_signals   = fmt_signals(general_inputs, 'reg')

        # Clock & reset signal declarations
        clk_rst_lines = []
        for c in clocks:
            clk_rst_lines.append(f"reg {c['name']} = 0;")
        for r in resets:
            clk_rst_lines.append(f"reg {r['name']};")
        clock_res_signals_str = '\n'.join(clk_rst_lines)

        # ── 1.5 Parameters ───────────────────────────────────────────────────
        param_decls = []
        param_maps  = []
        for p in parsed_data.get('parameters', []):
            param_decls.append(f"parameter {p['name']} = {p['value']};")
            param_maps.append(f".{p['name']}({p['name']})")
        param_decl_str = '\n'.join(param_decls)
        param_map_str  = f"#({', '.join(param_maps)})" if param_maps else ""

        # ── 2. Port Map ────────────────────────────────────────────────
        # Build tb-signal lookup: dut_port_name → tb_signal_name
        # Process clocks first, then resets; later entries overwrite earlier ones
        # if two entries share the same DUT port (user configuration conflict).
        port_to_tb = {}          # {dut_port: tb_signal_name}
        port_to_tb_src = {}      # {dut_port: 'clock'|'reset'} for conflict comments
        for c in clocks:
            dpt = c.get('port', c['name'])
            port_to_tb[dpt]     = c['name']
            port_to_tb_src[dpt] = 'clock'
        for r in resets:
            dpt = r.get('port', r['name'])
            if dpt in port_to_tb and port_to_tb[dpt] != r['name']:
                # Conflict: both a clock and a reset map to same DUT port
                # Keep the reset (it will assert/de-assert), but flag it
                port_to_tb_src[dpt] = f'CONFLICT: clock={port_to_tb[dpt]} overridden by reset={r["name"]}'
            else:
                port_to_tb_src[dpt] = 'reset'
            port_to_tb[dpt] = r['name']

        port_mapping = []
        for p_type in ('inputs', 'outputs', 'inouts'):
            for item in parsed_data.get(p_type, []):
                dut_port = item['name']
                tb_sig   = port_to_tb.get(dut_port, dut_port)  # remap if renamed
                if tb_sig != dut_port:
                    src = port_to_tb_src.get(dut_port, '')
                    conflict_note = f'  // *** {src} ***' if 'CONFLICT' in src else f'  // {src}: {tb_sig} → .{dut_port}'
                    port_mapping.append(f"    .{dut_port}({tb_sig}){conflict_note}")
                else:
                    port_mapping.append(f"    .{dut_port}({tb_sig})")
        port_map_str = ',\n'.join(port_mapping)

        # ── 3. Multiple Clock Generations ───────────────────────────────────
        clock_gen_lines = []
        for c in clocks:
            freq = float(c.get('frequency_mhz', 100.0))
            duty = float(c.get('duty_cycle', 50.0))
            period_ns = 1000.0 / freq
            name = c['name']
            if duty == 50.0:
                hp = period_ns / 2.0
                clock_gen_lines.append(f"always #{hp:.3f} {name} = ~{name};")
            else:
                hi = period_ns * (duty / 100.0)
                lo = period_ns - hi
                clock_gen_lines += [
                    f"always begin",
                    f"    {name} = 1'b1; #{hi:.3f};",
                    f"    {name} = 1'b0; #{lo:.3f};",
                    f"end",
                ]
        clock_gen_str = '\n'.join(clock_gen_lines)

        # ── 4. Initial Block ────────────────────────────────────────────────
        initial_lines = ["initial begin"]

        # 4a. Signal initialisation + parallel/sequential release
        #
        # New config keys: init_val, final_val, timing ('parallel'|'sequential'), auto
        # Legacy keys still accepted: active_low, auto_reset
        #
        # Model:
        #   T=0   → ALL auto signals are set to their init value simultaneously
        #   Then  → parallel signals release inside a single fork...join (absolute time)
        #   Then  → sequential signals fire one after another (relative delay from prev)

        def _resolve(r):
            """Normalise a reset/enable config dict to new-style keys."""
            if 'init_val' in r:
                return r                          # already new format
            # Legacy: active_low → init=0/final=1 or init=1/final=0
            al = r.get('active_low', True)
            return {
                'name':      r['name'],
                'sig_type':  'Reset',
                'init_val':  '0' if al else '1',
                'final_val': '1' if al else '0',
                'delay_ns':  r.get('delay_ns', 100),
                'auto':      r.get('auto_reset', r.get('auto', True)),
                'timing':    r.get('timing', 'parallel'),
                'port':      r.get('port', r['name']),
            }

        resolved     = [_resolve(r) for r in resets]
        auto_sigs    = [r for r in resolved if r.get('auto', True)]

        if general_inputs:
            initial_lines.append("    // ── Initialize inputs to 0 at T=0 ───────────────────────────────")
            for item in general_inputs:
                if item.get('width'):
                    initial_lines.append(f"    {item['name']} = 0;")
                else:
                    initial_lines.append(f"    {item['name']} = 1'b0;")
            initial_lines.append("    ")

        if auto_sigs:
            initial_lines.append("    // ── Set initial control values at T=0 ──────────────────────────")
            for r in auto_sigs:
                comment = f"  // {r['sig_type']}: {r['init_val']}→{r['final_val']}"
                initial_lines.append(f"    {r['name']} = 1'b{r['init_val']};{comment}")
            initial_lines.append("    ")

            initial_lines.append("    // ── Control Sequence ───────────────────────────────────────────")
            # Group adjacent signals where `timing` == 'parallel'. Isolated signals run sequentially.
            groups = []
            i = 0
            while i < len(auto_sigs):
                r = auto_sigs[i]
                if r.get('timing', 'sequential') == 'parallel':
                    batch = [r]
                    i += 1
                    while i < len(auto_sigs) and auto_sigs[i].get('timing', 'sequential') == 'parallel':
                        batch.append(auto_sigs[i])
                        i += 1
                    groups.append(batch)
                else:
                    groups.append([r])
                    i += 1

            def _get_delay(r):
                val = r.get('delay_ns', 100.0)
                if r.get('delay_unit', 'ns') == 'cycles':
                    cycles = int(val)
                    clk = r.get('delay_clock', 'clk')
                    return f"repeat({cycles}) @(posedge {clk});" if cycles > 0 else ""
                else:
                    return f"#{val:.1f};"

            for grp in groups:
                if len(grp) == 1:
                    r = grp[0]
                    delay_stmt = _get_delay(r)
                    initial_lines.append(f"    // {r['sig_type']}: {r['name']}")
                    if delay_stmt:
                        initial_lines.append(f"    {delay_stmt}")
                    initial_lines.append(f"    {r['name']} = 1'b{r['final_val']};")
                else:
                    initial_lines.append("    fork")
                    for r in grp:
                        delay_stmt = _get_delay(r)
                        initial_lines.append(f"        begin  // {r['sig_type']}: {r['name']}")
                        if delay_stmt:
                            initial_lines.append(f"            {delay_stmt}")
                        initial_lines.append(f"            {r['name']} = 1'b{r['final_val']};")
                        initial_lines.append( "        end")
                    initial_lines.append("    join")
            initial_lines.append("    ")

        # 4c. Sync to the first clock edge after all transitions are done
        primary_clk = clocks[0]['name'] if clocks else 'clk'
        initial_lines.append("    // Sync to clock edge — all init transitions are complete")
        initial_lines.append(f"    @(posedge {primary_clk});")
        initial_lines.append("    ")

        # 4d. User task sequence — group consecutive same-type fork entries
        task_sequence = config.get('task_sequence', [])
        if task_sequence:
            initial_lines.append("    // ── User Task Sequence ────────────────────────────────────")

            # Group consecutive tasks that share the same (non-sequential) fork type
            # so they become a SINGLE fork block together instead of isolated ones.
            groups = []
            i = 0
            while i < len(task_sequence):
                ft = task_sequence[i].get('fork_type', 'sequential')
                if ft == 'sequential':
                    groups.append({'type': 'sequential', 'tasks': [task_sequence[i]]})
                    i += 1
                else:
                    batch = [task_sequence[i]]
                    i += 1
                    while i < len(task_sequence) and task_sequence[i].get('fork_type') == ft:
                        batch.append(task_sequence[i])
                        i += 1
                    groups.append({'type': ft, 'tasks': batch})

            for grp in groups:
                calls = []
                for ts in grp['tasks']:
                    tname = self._extract_task_name(ts['task_file'], config)
                    calls.append(f"        {tname or ('/* ' + ts['task_file'] + ' */')}();")

                if grp['type'] == 'sequential':
                    for c in calls:
                        initial_lines.append(c.lstrip())  # no indent prefix
                else:
                    join_kw = {
                        'fork...join':      'join',
                        'fork...join_any':  'join_any',
                        'fork...join_none': 'join_none',
                    }[grp['type']]
                    initial_lines.append("    fork")
                    initial_lines.extend(calls)
                    initial_lines.append(f"    {join_kw}")
            initial_lines.append("    ")

        initial_lines.append("    // Observe final state")
        initial_lines.append("    #500;")
        initial_lines.append("    $finish;")
        initial_lines.append("end")

        # ── 5. Task Definitions (from library) ───────────────────────────────
        library_tasks = config.get('library_tasks', [])
        if library_tasks:
            tasks_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                'templates', 'tasks'
            )
            task_defs_lines = [
                "",
                "// ─────────────────────────────────────────────────────────────────────────",
                "// Task Definitions (from library)",
                "// ─────────────────────────────────────────────────────────────────────────",
            ]
            port_names = [p['name'] for p in (general_inputs + parsed_data.get('outputs', []))]
            for task_file in library_tasks:
                task_path = os.path.join(tasks_dir, task_file)
                try:
                    with open(task_path, 'r', encoding='utf-8') as fh:
                        raw = fh.read()

                    # Auto-map well-known signal patterns to actual DUT ports
                    raw = self._auto_map_ports(raw, port_names)
                    task_defs_lines.extend(raw.splitlines())
                    task_defs_lines.append("")
                except Exception as e:
                    task_defs_lines.append(f"// Error loading '{task_file}': {e}")

            initial_lines.extend(task_defs_lines)

        initial_block_str = '\n'.join(initial_lines)

        # ── 6. Fill template ─────────────────────────────────────────────────
        out = self.template
        out = out.replace("{MODULE_NAME}",           module_name)
        out = out.replace("{TB_MODULE_NAME}",        tb_name)
        out = out.replace("{PARAMETER_DECLARATIONS}", param_decl_str)
        out = out.replace("{PARAMETER_MAP}",         param_map_str)
        out = out.replace("{CLOCK_RES_SIGNALS}",     clock_res_signals_str)
        out = out.replace("{INPUT_SIGNALS}",         input_signals)
        out = out.replace("{OUTPUT_SIGNALS}",        output_signals)
        out = out.replace("{INOUT_SIGNALS}",         inout_signals)
        out = out.replace("{PORT_MAP}",              port_map_str)
        out = out.replace("{CLOCK_GENERATION}",      clock_gen_str)
        out = out.replace("{INITIAL_BLOCK}",         initial_block_str)

        return out

    # ──────────────────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _extract_task_name(self, task_file, config):
        """Return the first task name declared in the snippet file."""
        tasks_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            'templates', 'tasks'
        )
        task_path = os.path.join(tasks_dir, task_file)
        if not os.path.exists(task_path):
            return None
        try:
            with open(task_path, 'r', encoding='utf-8') as fh:
                raw = fh.read()
            m = re.search(r'\btask\s+(\w+)\s*;', raw)
            if m:
                return m.group(1)
        except Exception:
            pass
        return None

    def _auto_map_ports(self, raw_task: str, port_names: list) -> str:
        """Best-effort auto-mapping of placeholder signal names to actual DUT port names."""
        lower_ports = {p.lower(): p for p in port_names}

        def replace_if_match(pattern_name, raw, lower_ports):
            actual = lower_ports.get(pattern_name)
            if actual:
                raw = re.sub(r'\b' + re.escape(pattern_name) + r'\b', actual, raw)
            return raw

        # UART
        for pn in ['uart_rx', 'rxd']:
            actual = next((lower_ports[k] for k in lower_ports if 'rxd' in k or 'uart_rx' in k), None)
            if actual:
                raw_task = re.sub(r'\buart_tx\b', actual, raw_task)
                break
        for pn in ['uart_tx', 'txd']:
            actual = next((lower_ports[k] for k in lower_ports if 'txd' in k or 'uart_tx' in k), None)
            if actual:
                raw_task = re.sub(r'\buart_rx\b', actual, raw_task)
                break

        # SPI
        for placeholder, matcher in [('mosi', 'mosi'), ('miso', 'miso'), ('cs_n', 'cs'), ('sclk', 'sclk')]:
            actual = next((lower_ports[k] for k in lower_ports if matcher in k), None)
            if actual:
                raw_task = re.sub(r'\b' + re.escape(placeholder) + r'\b', actual, raw_task)

        return raw_task
