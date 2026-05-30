import sys
import re

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    with open('auditor_app.py', 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Imports
    content = content.replace(
        'from engine.ai_audit import analyze_files as ai_analyze_files',
        'from engine.ai_prompt import generate_ai_prompt'
    )

    # 2. Settings (exact line)
    content = content.replace('    "gemini_api_key": "",        # Google AI Studio free API key\n', '')

    # 3. Info Dialog updates
    content = content.replace(
        '2. AI AUDIT  (🤖 AI AUDIT button)',
        '2. COPY AI PROMPT  (📋 Copy AI Prompt button)'
    )
    content = content.replace(
        '   Sends each file to Google Gemini (gemini-2.0-flash) and asks\n'
        '   it to reason about the logic of the code. This catches errors\n'
        '   that rules cannot: wrong conditions, wrong variables, wrong\n'
        '   algorithms, etc. Takes ~5 seconds per file.',
        '   Generates an optimised prompt containing your code and strict\n'
        '   instructions to find logical errors. You paste it into ChatGPT/Claude\n'
        '   to catch errors rules cannot: wrong conditions, wrong algorithms, etc.'
    )
    content = content.replace('Found by Gemini AI.', 'Found by an AI assistant.')
    content = content.replace(
        "6. Click '🤖 AI AUDIT' for deep logical analysis (needs Gemini API key).",
        "6. Click '📋 Copy AI Prompt' and paste it to ChatGPT/Claude for logic analysis."
    )
    content = content.replace(
        'then run AI AUDIT on the cleaned-up code for best results.',
        'then use the AI Prompt on the cleaned-up code for best results.'
    )

    # 4. Remove Gemini AI Audit section from Settings Dialog
    s_idx = content.find('# ── Gemini AI Audit ──')
    e_idx = content.find('    def _toggle_key_vis(self):')
    if s_idx != -1 and e_idx != -1:
        e_idx2 = content.find('    def _on_editor_change(self):')
        content = content[:s_idx] + content[e_idx2:]

    content = content.replace('        self.settings["gemini_api_key"] = self._key_entry.get().strip()\n', '')

    # 5. Change Button text and padding
    content = content.replace('🤖  AI AUDIT  (Logical Errors)', '📋  COPY AI PROMPT')
    content = content.replace('command=self._start_ai_audit, pady=7', 'command=self._start_ai_audit, pady=10')

    # 6. Replace _start_ai_audit and remove _on_ai_progress / _on_ai_done ONLY
    new_method = '''    def _start_ai_audit(self):
        paths = list(self._target_listbox.get(0, "end"))
        if not paths:
            messagebox.showwarning("No Targets",
                                   "Add at least one folder or file before generating a prompt.")
            return

        from engine.scanner import collect_python_files
        file_paths = collect_python_files(paths)
        if not file_paths:
            messagebox.showwarning("No Files", "No Python files found in the selected targets.")
            return

        from engine.ai_prompt import generate_ai_prompt
        prompt = generate_ai_prompt(file_paths)
        if not prompt:
            messagebox.showerror("Error", "Could not read the selected files.")
            return

        self.root.clipboard_clear()
        self.root.clipboard_append(prompt)
        
        n = len(file_paths)
        messagebox.showinfo(
            "Prompt Copied!", 
            f"AI Prompt for {n} file(s) copied to clipboard!\\n\\n"
            "Paste this directly into ChatGPT (GPT-4o), Claude 3.5 Sonnet, or Gemini 1.5 Pro to get a deep logical audit."
        )'''

    s_start = content.find('    def _start_ai_audit(self):')
    e_end = content.find('    def _open_settings(self):')
    if s_start != -1 and e_end != -1:
        content = content[:s_start] + new_method + '\n\n' + content[e_end:]

    with open('auditor_app.py', 'w', encoding='utf-8') as f:
        f.write(content)

if __name__ == '__main__':
    main()
