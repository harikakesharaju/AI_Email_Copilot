#!/usr/bin/env python3
"""Test script to check how a specific email gets classified."""

import sys
sys.path.insert(0, '.')

from app.services.llm import classify_and_extract

# The email from Siri
subject = "Interview confirmation request"
body = """Hi Harika,

I'm writing to confirm your availability for interview on Wednesday at 10 am.
Please reply to this email and confirm whether you will be available at scheduled time. If timing isn't convenient, please let me know your preferred time.

Once you confirm, I'll send meeting details.

Thank you

Siri
Talent Acquisition Team"""

print("Testing email classification...")
print("=" * 60)
print(f"Subject: {subject}")
print(f"Body: {body[:100]}...")
print("=" * 60)

result = classify_and_extract(body, subject)

print("\nClassification Result:")
print(f"  Category:        {result['category']}")
print(f"  Priority:        {result['priority']}")
print(f"  Awaiting Reply:  {result['awaiting_reply']}")
print(f"  Confidence:      {result['confidence']:.2f}")
print(f"  Summary:         {result['summary']}")
print(f"  Tasks:           {len(result['tasks'])} task(s)")
for i, task in enumerate(result['tasks'], 1):
    print(f"    {i}. {task['description']}")
    if task['deadline']:
        print(f"       Deadline: {task['deadline']}")

print("\n" + "=" * 60)
if result['confidence'] >= 0.60:
    print("✅ PASS: Confidence >= 0.60, draft WILL be generated")
else:
    print(f"❌ FAIL: Confidence {result['confidence']:.2f} < 0.60, draft will NOT be generated")
print("=" * 60)
