/**
 * MediCure Premium Date Picker
 * A modern, accessible dropdown date picker with year/month selects and
 * calendar grid. Automatically replaces all <input type="date"> elements.
 *
 * Styled to match the MediCureFlow design system.
 */
(function () {
    'use strict';

    const MONTH_NAMES = [
        'January', 'February', 'March', 'April', 'May', 'June',
        'July', 'August', 'September', 'October', 'November', 'December'
    ];
    const DAY_LABELS = ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'];

    /* ---------- helpers ---------- */
    function pad(n) { return n < 10 ? '0' + n : '' + n; }

    function daysInMonth(y, m) { return new Date(y, m + 1, 0).getDate(); }

    function isoStr(d) {
        return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate());
    }

    function fmtDisplay(d) {
        return pad(d.getDate()) + ' ' + MONTH_NAMES[d.getMonth()].substring(0, 3) + ', ' + d.getFullYear();
    }

    function parseISO(str) {
        if (!str) return null;
        const parts = str.split('-');
        if (parts.length !== 3) return null;
        return new Date(+parts[0], +parts[1] - 1, +parts[2]);
    }

    let openPicker = null;   // currently open picker (singleton)
    let pickerIdCounter = 0;

    /* ---------- inject global CSS once ---------- */
    const STYLE = document.createElement('style');
    STYLE.textContent = `
/* ── MediCure DatePicker Reset ── */
.mcp-wrap{position:relative;display:inline-flex;width:100%}
.mcp-trigger{display:flex;align-items:center;gap:10px;width:100%;padding:14px 18px;border:2px solid #e8e8f0;border-radius:12px;font-size:.95rem;font-family:'Inter',sans-serif;color:#1a1a2e;background:#fafafa;cursor:pointer;transition:all .2s cubic-bezier(.4,0,.2,1);box-sizing:border-box;text-align:left;outline:none}
.mcp-trigger:hover{border-color:#c5c5d8}
.mcp-trigger:focus,.mcp-trigger.active{border-color:#4834d4;background:#fff;box-shadow:0 0 0 4px rgba(72,52,212,.1)}
.mcp-trigger svg{flex-shrink:0;color:#888}
.mcp-trigger .mcp-text{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.mcp-trigger .mcp-placeholder{color:#94a3b8}

/* dropdown panel */
.mcp-panel{position:absolute;top:calc(100% + 6px);left:0;z-index:9999;background:#fff;border:1px solid #e2e8f0;border-radius:16px;box-shadow:0 20px 50px rgba(0,0,0,.14);padding:20px;min-width:310px;opacity:0;transform:translateY(-8px) scale(.97);pointer-events:none;transition:all .2s cubic-bezier(.4,0,.2,1)}
.mcp-panel.open{opacity:1;transform:translateY(0) scale(1);pointer-events:auto}

/* selects row */
.mcp-selects{display:flex;gap:8px;margin-bottom:16px}
.mcp-sel{flex:1;padding:8px 12px;border:1.5px solid #e2e8f0;border-radius:10px;font-size:.85rem;font-family:'Inter',sans-serif;color:#1a1a2e;background:#fafafa;cursor:pointer;outline:none;appearance:auto;-webkit-appearance:auto;transition:border-color .15s}
.mcp-sel:focus{border-color:#4834d4;box-shadow:0 0 0 3px rgba(72,52,212,.1)}

/* calendar grid */
.mcp-cal{width:100%;border-collapse:collapse;table-layout:fixed}
.mcp-cal th{padding:6px 0;font-size:.72rem;font-weight:600;color:#94a3b8;text-transform:uppercase;text-align:center}
.mcp-cal td{text-align:center;padding:2px}
.mcp-day{width:36px;height:36px;border:none;background:transparent;border-radius:10px;font-size:.85rem;font-family:'Inter',sans-serif;color:#374151;cursor:pointer;transition:all .15s;outline:none;display:inline-flex;align-items:center;justify-content:center}
.mcp-day:hover:not(.sel):not(.dis){background:#f3f0ff;color:#4834d4}
.mcp-day.today:not(.sel){font-weight:700;color:#4834d4;position:relative}
.mcp-day.today:not(.sel)::after{content:'';position:absolute;bottom:3px;left:50%;transform:translateX(-50%);width:4px;height:4px;border-radius:50%;background:#4834d4}
.mcp-day.sel{background:linear-gradient(135deg,#4834d4,#686de0);color:#fff;font-weight:600;box-shadow:0 4px 12px rgba(72,52,212,.25)}
.mcp-day.out{color:#cbd5e1}
.mcp-day.dis{color:#e2e8f0;cursor:default}

/* footer */
.mcp-foot{display:flex;justify-content:space-between;align-items:center;margin-top:14px;padding-top:12px;border-top:1px solid #f1f5f9}
.mcp-btn{padding:7px 16px;border:none;border-radius:8px;font-size:.8rem;font-weight:600;font-family:'Inter',sans-serif;cursor:pointer;transition:all .15s}
.mcp-btn-ghost{background:transparent;color:#64748b}.mcp-btn-ghost:hover{background:#f1f5f9;color:#334155}
.mcp-btn-primary{background:linear-gradient(135deg,#4834d4,#686de0);color:#fff;box-shadow:0 4px 12px rgba(72,52,212,.2)}.mcp-btn-primary:hover{box-shadow:0 6px 16px rgba(72,52,212,.3);transform:translateY(-1px)}
.mcp-btn:disabled{opacity:.4;cursor:default;transform:none!important;box-shadow:none!important}
`;
    document.head.appendChild(STYLE);

    /* ---------- close on outside click ---------- */
    document.addEventListener('mousedown', function (e) {
        if (openPicker && !openPicker.wrap.contains(e.target)) {
            openPicker.close();
        }
    });
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && openPicker) openPicker.close();
    });

    /* ---------- Picker class ---------- */
    function MediCureDatePicker(input) {
        this.id = 'mcp-' + (++pickerIdCounter);
        this.input = input;
        this.value = parseISO(input.value) || null;
        this.viewYear = (this.value || new Date()).getFullYear();
        this.viewMonth = (this.value || new Date()).getMonth();

        this._build();
        this._render();
    }

    MediCureDatePicker.prototype._build = function () {
        var self = this;
        var input = this.input;

        // Hide original
        input.type = 'hidden';

        // Wrapper
        this.wrap = document.createElement('div');
        this.wrap.className = 'mcp-wrap';
        input.parentNode.insertBefore(this.wrap, input);
        this.wrap.appendChild(input);

        // Trigger button
        this.trigger = document.createElement('button');
        this.trigger.type = 'button';
        this.trigger.className = 'mcp-trigger';
        this.trigger.innerHTML =
            '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>' +
            '<span class="mcp-text mcp-placeholder">dd-mm-yyyy</span>';
        this.wrap.appendChild(this.trigger);

        // Panel
        this.panel = document.createElement('div');
        this.panel.className = 'mcp-panel';

        // — Year / Month selects —
        var selRow = document.createElement('div');
        selRow.className = 'mcp-selects';

        this.yearSel = document.createElement('select');
        this.yearSel.className = 'mcp-sel';
        var curYear = new Date().getFullYear();
        for (var y = curYear - 80; y <= curYear + 20; y++) {
            var o = document.createElement('option');
            o.value = y;
            o.textContent = y;
            this.yearSel.appendChild(o);
        }
        this.yearSel.value = this.viewYear;
        selRow.appendChild(this.yearSel);

        this.monthSel = document.createElement('select');
        this.monthSel.className = 'mcp-sel';
        for (var m = 0; m < 12; m++) {
            var o2 = document.createElement('option');
            o2.value = m;
            o2.textContent = MONTH_NAMES[m];
            this.monthSel.appendChild(o2);
        }
        this.monthSel.value = this.viewMonth;
        selRow.appendChild(this.monthSel);

        this.panel.appendChild(selRow);

        // — Calendar table —
        this.table = document.createElement('table');
        this.table.className = 'mcp-cal';
        this.panel.appendChild(this.table);

        // — Footer —
        var foot = document.createElement('div');
        foot.className = 'mcp-foot';

        this.clearBtn = document.createElement('button');
        this.clearBtn.type = 'button';
        this.clearBtn.className = 'mcp-btn mcp-btn-ghost';
        this.clearBtn.textContent = 'Clear';
        foot.appendChild(this.clearBtn);

        this.todayBtn = document.createElement('button');
        this.todayBtn.type = 'button';
        this.todayBtn.className = 'mcp-btn mcp-btn-primary';
        this.todayBtn.textContent = 'Today';
        foot.appendChild(this.todayBtn);

        this.panel.appendChild(foot);
        this.wrap.appendChild(this.panel);

        /* ---- events ---- */
        this.trigger.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            if (self.panel.classList.contains('open')) {
                self.close();
            } else {
                self.open();
            }
        });

        this.yearSel.addEventListener('change', function () {
            self.viewYear = +this.value;
            self._renderCal();
        });
        this.monthSel.addEventListener('change', function () {
            self.viewMonth = +this.value;
            self._renderCal();
        });

        this.clearBtn.addEventListener('click', function (e) {
            e.preventDefault();
            self.setValue(null);
            self.close();
        });
        this.todayBtn.addEventListener('click', function (e) {
            e.preventDefault();
            var today = new Date();
            self.viewYear = today.getFullYear();
            self.viewMonth = today.getMonth();
            self.setValue(today);
            self.close();
        });
    };

    MediCureDatePicker.prototype.open = function () {
        if (openPicker && openPicker !== this) openPicker.close();
        openPicker = this;
        this.trigger.classList.add('active');

        // Sync selects to current view
        this.yearSel.value = this.viewYear;
        this.monthSel.value = this.viewMonth;
        this._renderCal();

        this.panel.classList.add('open');
    };

    MediCureDatePicker.prototype.close = function () {
        this.panel.classList.remove('open');
        this.trigger.classList.remove('active');
        if (openPicker === this) openPicker = null;
    };

    MediCureDatePicker.prototype.setValue = function (date) {
        this.value = date;
        if (date) {
            this.input.value = isoStr(date);
            this.trigger.querySelector('.mcp-text').textContent = fmtDisplay(date);
            this.trigger.querySelector('.mcp-text').classList.remove('mcp-placeholder');
        } else {
            this.input.value = '';
            this.trigger.querySelector('.mcp-text').textContent = 'dd-mm-yyyy';
            this.trigger.querySelector('.mcp-text').classList.add('mcp-placeholder');
        }
        // Fire change event so Django / JS listeners react
        this.input.dispatchEvent(new Event('change', { bubbles: true }));
    };

    MediCureDatePicker.prototype._render = function () {
        if (this.value) {
            this.trigger.querySelector('.mcp-text').textContent = fmtDisplay(this.value);
            this.trigger.querySelector('.mcp-text').classList.remove('mcp-placeholder');
        }
        this._renderCal();
    };

    MediCureDatePicker.prototype._renderCal = function () {
        var self = this;
        var y = this.viewYear, m = this.viewMonth;
        var today = new Date();
        var tY = today.getFullYear(), tM = today.getMonth(), tD = today.getDate();

        var html = '<thead><tr>';
        DAY_LABELS.forEach(function (d) { html += '<th>' + d + '</th>'; });
        html += '</tr></thead><tbody>';

        var first = new Date(y, m, 1).getDay();   // 0-6
        var total = daysInMonth(y, m);
        var prevTotal = daysInMonth(y, m - 1);

        var day = 1;
        var nextDay = 1;
        for (var row = 0; row < 6; row++) {
            html += '<tr>';
            for (var col = 0; col < 7; col++) {
                var cellIndex = row * 7 + col;
                if (cellIndex < first) {
                    // previous month
                    var pd = prevTotal - first + cellIndex + 1;
                    html += '<td><button type="button" class="mcp-day out" data-day="" tabindex="-1">' + pd + '</button></td>';
                } else if (day > total) {
                    html += '<td><button type="button" class="mcp-day out" data-day="" tabindex="-1">' + (nextDay++) + '</button></td>';
                } else {
                    var cls = 'mcp-day';
                    if (y === tY && m === tM && day === tD) cls += ' today';
                    if (self.value && y === self.value.getFullYear() && m === self.value.getMonth() && day === self.value.getDate()) cls += ' sel';
                    html += '<td><button type="button" class="' + cls + '" data-day="' + day + '">' + day + '</button></td>';
                    day++;
                }
            }
            html += '</tr>';
            if (day > total) break;
        }
        html += '</tbody>';
        this.table.innerHTML = html;

        // Attach click handlers
        this.table.querySelectorAll('.mcp-day[data-day]').forEach(function (btn) {
            btn.addEventListener('click', function (e) {
                e.preventDefault();
                e.stopPropagation();
                var d = +btn.getAttribute('data-day');
                if (!d) return;
                var picked = new Date(self.viewYear, self.viewMonth, d);
                self.setValue(picked);
                self.close();
            });
        });
    };

    /* ---------- Auto-init ---------- */
    function initAll() {
        document.querySelectorAll('input[type="date"]:not([data-mcp])').forEach(function (input) {
            input.setAttribute('data-mcp', 'true');
            new MediCureDatePicker(input);
        });
    }

    // Run on DOMContentLoaded and also expose for dynamic content
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initAll);
    } else {
        initAll();
    }

    // Observe DOM for dynamically added inputs (modals, AJAX, etc.)
    var observer = new MutationObserver(function () { initAll(); });
    observer.observe(document.body || document.documentElement, { childList: true, subtree: true });

    // Expose globally
    window.MediCureDatePicker = MediCureDatePicker;
    window.initMediCureDatePickers = initAll;
})();
