import file_modifier

code1 = """
with open('output.txt', 'w') as f:
    f.write('hello world')
"""

b, name, err = file_modifier._safe_exec(code1, b"")
print("Test 1 Output:", b, name, err)

code2 = """
with open('input.txt', 'r') as f:
    data = f.read()

with open('output2.txt', 'w') as f:
    f.write(data + " appended")
"""
b2, name2, err2 = file_modifier._safe_exec(code2, b"initial")
print("Test 2 Output:", b2, name2, err2)

code3 = """
with open('/etc/passwd', 'r') as f:
    data = f.read()
"""
b3, name3, err3 = file_modifier._safe_exec(code3, b"hello")
print("Test 3 Output (read any file gives input_bytes):", b3, name3[:20] if name3 else None, err3)

code4 = """
output_buffer.write('direct write'.encode())
output_filename = 'direct.txt'
"""
b4, name4, err4 = file_modifier._safe_exec(code4, b"")
print("Test 4 Output:", b4, name4, err4)
