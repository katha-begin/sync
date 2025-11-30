# Settings Tab UI for F2L Application
# This file contains the setup_settings_tab method to be added to f2l_complete.py

def setup_settings_tab(self, notebook):
    """Setup performance and scan settings tab"""
    # Create main frame for the tab
    settings_tab = ttk.Frame(notebook)
    notebook.add(settings_tab, text="⚙️ Settings")

    # Create canvas and scrollbar for scrollable content
    canvas = tk.Canvas(settings_tab, highlightthickness=0)
    scrollbar = ttk.Scrollbar(settings_tab, orient="vertical", command=canvas.yview)
    settings_frame = ttk.Frame(canvas)

    # Configure canvas scrolling
    settings_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )

    canvas.create_window((0, 0), window=settings_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    # Pack canvas and scrollbar
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    # Enable mousewheel scrolling
    def _on_mousewheel(event):
        canvas.yview_scroll(int(-1*(event.delta/120)), "units")
    canvas.bind_all("<MouseWheel>", _on_mousewheel)

    # Title
    title_frame = ttk.Frame(settings_frame)
    title_frame.pack(fill=tk.X, padx=10, pady=10)

    ttk.Label(title_frame, text="Performance & Scan Settings",
             font=('TkDefaultFont', 12, 'bold')).pack(anchor='w')
    ttk.Label(title_frame, text="Configure scanning performance, caching, and memory usage",
             foreground='gray').pack(anchor='w')

    # ===== LOCAL SCAN SETTINGS =====
    local_frame = ttk.LabelFrame(settings_frame, text="Local Directory Scanning", padding=10)
    local_frame.pack(fill=tk.X, padx=10, pady=5)

    # Parallel scanning
    parallel_frame = ttk.Frame(local_frame)
    parallel_frame.pack(fill=tk.X, pady=5)

    self.settings_local_parallel_var = tk.BooleanVar(value=self.scan_config["local_parallel_enabled"])
    ttk.Checkbutton(parallel_frame, text="Enable Parallel Scanning",
                   variable=self.settings_local_parallel_var).pack(side=tk.LEFT)
    ttk.Label(parallel_frame, text="(Faster for large directories)",
             foreground='gray', font=('TkDefaultFont', 8)).pack(side=tk.LEFT, padx=5)

    # Thread count
    workers_frame = ttk.Frame(local_frame)
    workers_frame.pack(fill=tk.X, pady=5)

    ttk.Label(workers_frame, text="Parallel Threads:").pack(side=tk.LEFT)
    self.settings_local_workers_var = tk.IntVar(value=self.scan_config["local_max_workers"])
    workers_spin = ttk.Spinbox(workers_frame, from_=1, to=16, width=10,
                               textvariable=self.settings_local_workers_var)
    workers_spin.pack(side=tk.LEFT, padx=5)
    ttk.Label(workers_frame, text="(1-16 threads, recommended: 4-8)",
             foreground='gray', font=('TkDefaultFont', 8)).pack(side=tk.LEFT)

    # ===== FTP SCAN SETTINGS =====
    ftp_frame = ttk.LabelFrame(settings_frame, text="FTP Scanning", padding=10)
    ftp_frame.pack(fill=tk.X, padx=10, pady=5)

    # Max files
    max_files_frame = ttk.Frame(ftp_frame)
    max_files_frame.pack(fill=tk.X, pady=5)

    ttk.Label(max_files_frame, text="Maximum Files to Scan:").pack(side=tk.LEFT)
    self.settings_ftp_max_files_var = tk.IntVar(value=self.scan_config["ftp_max_files"])
    max_files_spin = ttk.Spinbox(max_files_frame, from_=10000, to=2000000, increment=50000,
                                 width=15, textvariable=self.settings_ftp_max_files_var)
    max_files_spin.pack(side=tk.LEFT, padx=5)
    ttk.Label(max_files_frame, text="(10k - 2M files)",
             foreground='gray', font=('TkDefaultFont', 8)).pack(side=tk.LEFT)

    # Smart filter
    smart_filter_frame = ttk.Frame(ftp_frame)
    smart_filter_frame.pack(fill=tk.X, pady=5)

    self.settings_ftp_smart_filter_var = tk.BooleanVar(value=self.scan_config["ftp_smart_filter"])
    ttk.Checkbutton(smart_filter_frame, text="Smart Folder-First Scanning",
                   variable=self.settings_ftp_smart_filter_var).pack(side=tk.LEFT)
    ttk.Label(smart_filter_frame, text="(Only scan filtered folders when filter enabled - much faster)",
             foreground='gray', font=('TkDefaultFont', 8)).pack(side=tk.LEFT, padx=5)

    # Show warnings
    warnings_frame = ttk.Frame(ftp_frame)
    warnings_frame.pack(fill=tk.X, pady=5)

    self.settings_ftp_warnings_var = tk.BooleanVar(value=self.scan_config["ftp_show_warnings"])
    ttk.Checkbutton(warnings_frame, text="Show Warnings When Limits Reached",
                   variable=self.settings_ftp_warnings_var).pack(side=tk.LEFT)
    ttk.Label(warnings_frame, text="(Alert when file limit is hit)",
             foreground='gray', font=('TkDefaultFont', 8)).pack(side=tk.LEFT, padx=5)

    # ===== CACHE SETTINGS =====
    cache_frame = ttk.LabelFrame(settings_frame, text="Scan Caching", padding=10)
    cache_frame.pack(fill=tk.X, padx=10, pady=5)

    # Enable cache
    cache_enable_frame = ttk.Frame(cache_frame)
    cache_enable_frame.pack(fill=tk.X, pady=5)

    self.settings_cache_enabled_var = tk.BooleanVar(value=self.scan_config["cache_enabled"])
    ttk.Checkbutton(cache_enable_frame, text="Enable Scan Result Caching",
                   variable=self.settings_cache_enabled_var).pack(side=tk.LEFT)
    ttk.Label(cache_enable_frame, text="(Reuse recent scan results for faster subsequent scans)",
             foreground='gray', font=('TkDefaultFont', 8)).pack(side=tk.LEFT, padx=5)

    # Cache duration
    cache_duration_frame = ttk.Frame(cache_frame)
    cache_duration_frame.pack(fill=tk.X, pady=5)

    ttk.Label(cache_duration_frame, text="Cache Duration:").pack(side=tk.LEFT)
    self.settings_cache_duration_var = tk.IntVar(value=self.scan_config["cache_duration"])
    cache_duration_spin = ttk.Spinbox(cache_duration_frame, from_=60, to=3600, increment=60,
                                      width=10, textvariable=self.settings_cache_duration_var)
    cache_duration_spin.pack(side=tk.LEFT, padx=5)
    ttk.Label(cache_duration_frame, text="seconds (1-60 minutes)",
             foreground='gray', font=('TkDefaultFont', 8)).pack(side=tk.LEFT)

    # Cache info
    cache_info_frame = ttk.Frame(cache_frame)
    cache_info_frame.pack(fill=tk.X, pady=5)
    ttk.Label(cache_info_frame, text="ℹ️ Cached scans are reused if directory hasn't changed",
             foreground='blue', font=('TkDefaultFont', 8)).pack(anchor='w')

    # ===== MEMORY SETTINGS =====
    memory_frame = ttk.LabelFrame(settings_frame, text="Memory Optimization", padding=10)
    memory_frame.pack(fill=tk.X, padx=10, pady=5)

    # Memory efficient mode
    memory_efficient_frame = ttk.Frame(memory_frame)
    memory_efficient_frame.pack(fill=tk.X, pady=5)

    self.settings_memory_efficient_var = tk.BooleanVar(value=self.scan_config["memory_efficient"])
    ttk.Checkbutton(memory_efficient_frame, text="Memory-Efficient Mode",
                   variable=self.settings_memory_efficient_var).pack(side=tk.LEFT)
    ttk.Label(memory_efficient_frame, text="(Use streaming/chunked processing for large datasets)",
             foreground='gray', font=('TkDefaultFont', 8)).pack(side=tk.LEFT, padx=5)

    # Max memory
    max_memory_frame = ttk.Frame(memory_frame)
    max_memory_frame.pack(fill=tk.X, pady=5)

    ttk.Label(max_memory_frame, text="Maximum Memory Usage:").pack(side=tk.LEFT)
    self.settings_max_memory_var = tk.IntVar(value=self.scan_config["max_memory_mb"])
    max_memory_spin = ttk.Spinbox(max_memory_frame, from_=128, to=4096, increment=128,
                                  width=10, textvariable=self.settings_max_memory_var)
    max_memory_spin.pack(side=tk.LEFT, padx=5)
    ttk.Label(max_memory_frame, text="MB (128 MB - 4 GB)",
             foreground='gray', font=('TkDefaultFont', 8)).pack(side=tk.LEFT)

    # ===== ADVANCED SETTINGS =====
    advanced_frame = ttk.LabelFrame(settings_frame, text="Advanced Settings", padding=10)
    advanced_frame.pack(fill=tk.X, padx=10, pady=5)

    # Max depth
    max_depth_frame = ttk.Frame(advanced_frame)
    max_depth_frame.pack(fill=tk.X, pady=5)

    ttk.Label(max_depth_frame, text="Maximum Directory Depth:").pack(side=tk.LEFT)
    self.settings_max_depth_var = tk.IntVar(value=self.scan_config["max_depth"])
    max_depth_spin = ttk.Spinbox(max_depth_frame, from_=10, to=200, increment=10,
                                 width=10, textvariable=self.settings_max_depth_var)
    max_depth_spin.pack(side=tk.LEFT, padx=5)
    ttk.Label(max_depth_frame, text="(Prevent infinite recursion)",
             foreground='gray', font=('TkDefaultFont', 8)).pack(side=tk.LEFT)

    # Chunk size
    chunk_size_frame = ttk.Frame(advanced_frame)
    chunk_size_frame.pack(fill=tk.X, pady=5)

    ttk.Label(chunk_size_frame, text="Progress Update Chunk Size:").pack(side=tk.LEFT)
    self.settings_chunk_size_var = tk.IntVar(value=self.scan_config["chunk_size"])
    chunk_size_spin = ttk.Spinbox(chunk_size_frame, from_=100, to=2000, increment=100,
                                  width=10, textvariable=self.settings_chunk_size_var)
    chunk_size_spin.pack(side=tk.LEFT, padx=5)
    ttk.Label(chunk_size_frame, text="files (100-2000)",
             foreground='gray', font=('TkDefaultFont', 8)).pack(side=tk.LEFT)

    # ===== ACTION BUTTONS =====
    action_frame = ttk.Frame(settings_frame)
    action_frame.pack(fill=tk.X, padx=10, pady=20)

    ttk.Button(action_frame, text="💾 Save Settings",
              command=self.apply_settings_from_ui,
              style='Accent.TButton').pack(side=tk.LEFT, padx=5)
    ttk.Button(action_frame, text="🔄 Reset to Defaults",
              command=self.reset_scan_settings).pack(side=tk.LEFT, padx=5)
    ttk.Button(action_frame, text="🗑️ Clear Cache",
              command=self.clear_scan_cache).pack(side=tk.LEFT, padx=5)

    # ===== PERFORMANCE TIPS =====
    tips_frame = ttk.LabelFrame(settings_frame, text="💡 Performance Tips", padding=10)
    tips_frame.pack(fill=tk.X, padx=10, pady=5)

    tips_text = """
• For filtered scans: Enable "Smart Folder-First Scanning" for 10-100x speed improvement
• For large directories: Increase parallel threads (4-8 recommended)
• For frequent scans: Enable caching with 5-10 minute duration
• For memory-constrained systems: Enable "Memory-Efficient Mode" and reduce max memory
• For very large FTP servers: Increase "Maximum Files to Scan" limit
• Cache is automatically cleared when directory structure changes
    """
    ttk.Label(tips_frame, text=tips_text.strip(), justify=tk.LEFT,
             foreground='#006400', font=('TkDefaultFont', 8)).pack(anchor='w')

    # ===== CURRENT STATUS =====
    status_frame = ttk.LabelFrame(settings_frame, text="Current Status", padding=10)
    status_frame.pack(fill=tk.X, padx=10, pady=5)

    self.settings_status_var = tk.StringVar(value="Settings loaded from database")
    ttk.Label(status_frame, textvariable=self.settings_status_var,
             font=('TkDefaultFont', 9)).pack(anchor='w')

