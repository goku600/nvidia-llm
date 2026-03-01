import file_modifier
import asyncio
import re

full_reply = """Great, I'll generate the PDF using loops to save tokens.

[PYTHON_EXEC]
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER

doc = SimpleDocTemplate(output_buffer)
styles = getSampleStyleSheet()
styleH = ParagraphStyle(name='Heading', parent=styles['Heading1'], alignment=TA_CENTER)
styleN = styles['Normal']

flowables = []
sections = ['Science', 'Math', 'English', 'General Knowledge']

for section in sections:
    flowables.append(Paragraph(f"Section: {section}", styleH))
    flowables.append(Spacer(1, 12))
    for i in range(1, 11):
        flowables.append(Paragraph(f"Question {i}: (Simulated Question Text for {section})", styleN))
        flowables.append(Paragraph("A) Option 1  B) Option 2  C) Option 3  D) Option 4", styleN))
        flowables.append(Spacer(1, 6))

doc.build(flowables)
output_filename = "scholarship_test_mock.pdf"
[/PYTHON_EXEC]
"""

async def main():
    print("Testing successful code block with ReportLab loops...\n")
    
    clean_reply_for_parsing = full_reply
    if "```python\n[PYTHON_EXEC]" in clean_reply_for_parsing:
        clean_reply_for_parsing = clean_reply_for_parsing.replace("```python\n[PYTHON_EXEC]", "[PYTHON_EXEC]")
    
    exec_start = clean_reply_for_parsing.find("[PYTHON_EXEC]")
    exec_end = clean_reply_for_parsing.find("[/PYTHON_EXEC]")
    
    if exec_start != -1 and exec_end != -1:
        code = clean_reply_for_parsing[exec_start + len("[PYTHON_EXEC]"):exec_end].strip()
        if code.endswith("```"):
            code = re.sub(r"\s*```$", "", code)
            
        print("Executing Sandbox Code:\n" + "="*40 + "\n" + code + "\n" + "="*40)
        output_bytes, output_filename, error = await asyncio.to_thread(
            file_modifier.execute_python_code, code, b""
        )
        if error:
            print("\n❌ Sandbox Error:\n", error)
        elif output_bytes:
            print(f"\n[SUCCESS] Generated {output_filename} ({len(output_bytes)} bytes)")
            with open(output_filename, "wb") as f:
                f.write(output_bytes)
    else:
        print("Block not found")

if __name__ == "__main__":
    asyncio.run(main())
