#!/usr/bin/env python3
"""
Local Testing Script for Adjnt
Run: python test_locally.py

This script lets you test your intent classification without WhatsApp.
"""

import asyncio
import json
from datetime import datetime
from brain import AdjntBrain
from colorama import init, Fore, Style

# Initialize colorama for colored output
init(autoreset=True)

# Test cases matching your requirements
TEST_CASES = [
    # TASK tests
    {"input": "add milk", "expected_intent": "TASK", "description": "Simple add"},
    {"input": "add 3 eggs to Safeway", "expected_intent": "TASK", "description": "Add with count and store"},
    {"input": "get 2 apples and 5 bananas from Costco", "expected_intent": "TASK", "description": "Add multiple items"},
    {"input": "buy tomatoes", "expected_intent": "TASK", "description": "Add with buy keyword"},
    
    # DELETE tests
    {"input": "remove 2 milk", "expected_intent": "DELETE", "description": "Remove specific count"},
    {"input": "remove milk from Safeway", "expected_intent": "DELETE", "description": "Remove from specific store"},
    {"input": "delete all apples", "expected_intent": "DELETE", "description": "Delete all of item"},
    {"input": "clear safeway", "expected_intent": "DELETE", "description": "Clear specific store only"},
    {"input": "clear list", "expected_intent": "DELETE", "description": "Clear entire vault"},
    {"input": "clear vault", "expected_intent": "DELETE", "description": "Clear entire vault (alternate)"},
    
    # MOVE tests
    {"input": "move bread from General to Costco", "expected_intent": "MOVE", "description": "Move single item"},
    {"input": "move oranges from Safeway to General", "expected_intent": "MOVE", "description": "Move all oranges (plural)"},
    {"input": "transfer eggs from Safeway to Target", "expected_intent": "MOVE", "description": "Transfer items"},
    
    # REMIND tests
    {"input": "remind me in 2 hours to walk dog", "expected_intent": "REMIND", "description": "Relative time reminder"},
    {"input": "Music class next Wednesday 5pm", "expected_intent": "REMIND", "description": "Specific date/time"},
    {"input": "dentist tomorrow at 3pm", "expected_intent": "REMIND", "description": "Tomorrow with time"},
    {"input": "meeting in 30 minutes", "expected_intent": "REMIND", "description": "Relative minutes"},
    {"input": "meet Jaideep on Saturday", "expected_intent": "REMIND", "description": "Date without time (should default to 9 AM)"},
    {"input": "lunch Friday 12:30pm", "expected_intent": "REMIND", "description": "Day with specific time"},
    
    # REMIND - Recurring tests (NEW)
    {"input": "standup meeting every day at 9am", "expected_intent": "REMIND", "description": "Daily recurring reminder"},
    {"input": "team meeting every Monday at 2pm", "expected_intent": "REMIND", "description": "Weekly recurring on specific day"},
    {"input": "dentist appointment every 6 months", "expected_intent": "REMIND", "description": "Monthly recurring with interval"},
    {"input": "gym every weekday at 6am", "expected_intent": "REMIND", "description": "Weekday recurring reminder"},
    {"input": "brunch every weekend at 11am", "expected_intent": "REMIND", "description": "Weekend recurring reminder"},
    {"input": "pay rent every month on the 1st", "expected_intent": "REMIND", "description": "Monthly recurring reminder"},
    {"input": "birthday reminder every year on March 15", "expected_intent": "REMIND", "description": "Yearly recurring reminder"},
    
    # DELETE_REMINDERS tests
    {"input": "delete music class on Wednesday", "expected_intent": "DELETE_REMINDERS", "description": "Delete specific reminder"},
    {"input": "delete all music class", "expected_intent": "DELETE_REMINDERS", "description": "Delete all matching reminders"},
    {"input": "cancel dentist appointment", "expected_intent": "DELETE_REMINDERS", "description": "Cancel appointment"},
    {"input": "remove meet neha", "expected_intent": "DELETE_REMINDERS", "description": "Remove meeting"},
    
    # UPDATE_REMINDER tests
    {"input": "change music class to 6pm", "expected_intent": "UPDATE_REMINDER", "description": "Change time"},
    {"input": "reschedule dentist to tomorrow 2pm", "expected_intent": "UPDATE_REMINDER", "description": "Reschedule to new date/time"},
    {"input": "move meeting to 4pm", "expected_intent": "UPDATE_REMINDER", "description": "Move reminder time"},
    
    # LIST tests
    {"input": "list", "expected_intent": "LIST", "description": "List all items"},
    {"input": "show vault", "expected_intent": "LIST", "description": "Show vault"},
    {"input": "show list", "expected_intent": "LIST", "description": "Show list"},
    
    # LIST_REMINDERS tests
    {"input": "list reminders", "expected_intent": "LIST_REMINDERS", "description": "List all reminders"},
    {"input": "show reminders", "expected_intent": "LIST_REMINDERS", "description": "Show reminders"},
    {"input": "my reminders", "expected_intent": "LIST_REMINDERS", "description": "My reminders"},
    
    # LIST_REMINDERS - Date filtering tests (NEW)
    {"input": "reminders for today", "expected_intent": "LIST_REMINDERS", "description": "Reminders for today"},
    {"input": "what are my plans tomorrow", "expected_intent": "LIST_REMINDERS", "description": "Plans for tomorrow"},
    {"input": "show me Saturday's schedule", "expected_intent": "LIST_REMINDERS", "description": "Schedule for Saturday"},
    {"input": "what's on my calendar this week", "expected_intent": "LIST_REMINDERS", "description": "This week's schedule"},
    {"input": "reminders for January 25", "expected_intent": "LIST_REMINDERS", "description": "Reminders for specific date"},
    {"input": "what do I have on Monday", "expected_intent": "LIST_REMINDERS", "description": "Monday's schedule"},
    
    # TIME tests (NEW)
    {"input": "what time is it", "expected_intent": "TIME", "description": "Current time"},
    {"input": "what's the time", "expected_intent": "TIME", "description": "Current time (alt)"},
    {"input": "time now", "expected_intent": "TIME", "description": "Time now"},
    
    # ONBOARD tests
    {"input": "help", "expected_intent": "ONBOARD", "description": "Help command"},
    {"input": "guide", "expected_intent": "ONBOARD", "description": "Guide command"},
    
    # CHAT tests
    {"input": "how are you?", "expected_intent": "CHAT", "description": "General conversation"},
    {"input": "what can you do?", "expected_intent": "CHAT", "description": "Capability question"},
]

class LocalTester:
    def __init__(self):
        self.brain = AdjntBrain()
        self.passed = 0
        self.failed = 0
        self.test_results = []
    
    async def test_single(self, text: str, expected_intent: str = None, description: str = None):
        """Test a single input."""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        try:
            result = await self.brain.decide(text, now_str)
            intent = result.get('intent')
            data = result.get('data', {})
            
            # Check if intent matches expected
            passed = False
            if expected_intent:
                if intent == expected_intent:
                    print(f"{Fore.GREEN}✓ PASS{Style.RESET_ALL}")
                    self.passed += 1
                    passed = True
                else:
                    print(f"{Fore.RED}✗ FAIL - Expected: {expected_intent}, Got: {intent}{Style.RESET_ALL}")
                    self.failed += 1
                
                # Store result for summary
                self.test_results.append({
                    "description": description or text,
                    "input": text,
                    "expected": expected_intent,
                    "actual": intent,
                    "passed": passed,
                    "data": data
                })
            else:
                print(f"{Fore.CYAN}Intent: {intent}{Style.RESET_ALL}")
            
            # Display parsed data with validation
            self._validate_and_display_data(intent, data)
            return result
            
        except Exception as e:
            print(f"{Fore.RED}ERROR: {e}{Style.RESET_ALL}")
            if expected_intent:
                self.failed += 1
                self.test_results.append({
                    "description": description or text,
                    "input": text,
                    "expected": expected_intent,
                    "actual": "ERROR",
                    "passed": False,
                    "error": str(e)
                })
            return None
    
    def _validate_and_display_data(self, intent: str, data: dict):
        """Validate data structure and display with color coding."""
        print(f"{Fore.YELLOW}Data:{Style.RESET_ALL}")
        
        # Intent-specific validation
        warnings = []
        
        if intent == "TASK":
            items = data.get('items', [])
            if not items:
                warnings.append("⚠️  No items found")
            else:
                for item in items:
                    # Check singularization
                    if item.get('name', '').endswith('s') and item['name'] not in ['glass', 'grass']:
                        warnings.append(f"⚠️  Item '{item['name']}' might not be singularized")
                    # Check store capitalization
                    store = item.get('store', '')
                    if store and not store[0].isupper():
                        warnings.append(f"⚠️  Store '{store}' should be capitalized")
        
        elif intent == "DELETE":
            mode = data.get('mode')
            if mode == "CLEAR_STORE" and not data.get('store'):
                warnings.append("⚠️  CLEAR_STORE mode but no store specified")
            elif mode == "CLEAR_ALL" and data.get('items'):
                warnings.append("⚠️  CLEAR_ALL mode should have empty items list")
            elif mode == "SINGLE":
                items = data.get('items', [])
                for item in items:
                    if 'count' not in item:
                        warnings.append(f"⚠️  SINGLE mode item missing count")
        
        elif intent == "MOVE":
            if not data.get('move_all'):
                warnings.append("⚠️  move_all flag not set (should default to true)")
            if data.get('item', '').endswith('s'):
                warnings.append(f"⚠️  Item '{data.get('item')}' might not be singularized")
        
        elif intent == "REMIND":
            has_minutes = 'minutes' in data
            has_timestamp = 'timestamp' in data
            recurrence = data.get('recurrence')
            
            if not has_minutes and not has_timestamp:
                warnings.append("⚠️  Missing both 'minutes' and 'timestamp'")
            if has_timestamp:
                ts = data.get('timestamp', '')
                # Check if timestamp is at midnight (00:00:00)
                if '00:00:00' in ts:
                    warnings.append("⚠️  Timestamp at midnight - should default to 09:00:00 for better UX")
            
            # Validate recurring reminders
            if recurrence:
                if recurrence == 'weekly' and 'day_of_week' in data:
                    day = data.get('day_of_week')
                    if day not in ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']:
                        warnings.append(f"⚠️  Invalid day_of_week: {day}")
                if recurrence == 'monthly' and 'interval' in data:
                    interval = data.get('interval')
                    if not isinstance(interval, int) or interval < 1:
                        warnings.append(f"⚠️  Invalid interval: {interval}")
        
        elif intent == "LIST_REMINDERS":
            date_filter = data.get('date_filter')
            if date_filter:
                valid_filters = ['today', 'tomorrow', 'this_week', 'Monday', 'Tuesday', 'Wednesday', 
                               'Thursday', 'Friday', 'Saturday', 'Sunday']
                # Also allow date strings like "2026-01-25"
                if date_filter not in valid_filters and not (len(date_filter) == 10 and '-' in date_filter):
                    warnings.append(f"⚠️  Unusual date_filter: {date_filter}")
        
        # Display data with nice formatting
        print(f"  {json.dumps(data, indent=2)}")
        
        # Show warnings
        if warnings:
            print(f"\n{Fore.YELLOW}Validation Warnings:{Style.RESET_ALL}")
            for warning in warnings:
                print(f"  {warning}")
        else:
            print(f"{Fore.GREEN}  ✓ Data structure looks good{Style.RESET_ALL}")
    
    async def run_all_tests(self):
        """Run all predefined test cases."""
        print(f"\n{Fore.CYAN}{'='*70}")
        print(f"RUNNING AUTOMATED TESTS")
        print(f"{'='*70}{Style.RESET_ALL}\n")
        
        for idx, test in enumerate(TEST_CASES, 1):
            print(f"\n{Fore.BLUE}[Test {idx}/{len(TEST_CASES)}]{Style.RESET_ALL} {test['description']}")
            print(f"{Fore.WHITE}Input: \"{test['input']}\"{Style.RESET_ALL}")
            await self.test_single(test['input'], test['expected_intent'], test['description'])
            print()
        
        # Print summary
        self._print_summary()
    
    def _print_summary(self):
        """Print test results summary."""
        total = self.passed + self.failed
        print(f"\n{Fore.CYAN}{'='*70}")
        print(f"TEST SUMMARY")
        print(f"{'='*70}{Style.RESET_ALL}")
        print(f"Total Tests: {total}")
        print(f"{Fore.GREEN}Passed: {self.passed} ({self.passed/total*100:.1f}%){Style.RESET_ALL}")
        if self.failed > 0:
            print(f"{Fore.RED}Failed: {self.failed} ({self.failed/total*100:.1f}%){Style.RESET_ALL}")
        print()
        
        # Group failures by intent
        if self.failed > 0:
            failures_by_intent = {}
            for result in self.test_results:
                if not result['passed']:
                    expected = result['expected']
                    if expected not in failures_by_intent:
                        failures_by_intent[expected] = []
                    failures_by_intent[expected].append(result)
            
            print(f"{Fore.RED}Failed Tests by Intent:{Style.RESET_ALL}\n")
            for intent, failures in failures_by_intent.items():
                print(f"{Fore.YELLOW}  {intent}:{Style.RESET_ALL}")
                for fail in failures:
                    print(f"    • {fail['description']}")
                    print(f"      Input: \"{fail['input']}\"")
                    print(f"      Expected: {fail['expected']}, Got: {fail['actual']}")
                print()
        
        # Show warnings summary
        warnings_count = sum(1 for r in self.test_results if 'data' in r and self._has_warnings(r.get('data', {})))
        if warnings_count > 0:
            print(f"{Fore.YELLOW}⚠️  {warnings_count} test(s) passed but have data validation warnings{Style.RESET_ALL}")
        
        print("=" * 70)
    
    def _has_warnings(self, data: dict) -> bool:
        """Check if data has potential issues."""
        # Quick check for common issues
        for item in data.get('items', []):
            if item.get('name', '').endswith('s'):
                return True
            store = item.get('store', '')
            if store and not store[0].isupper():
                return True
        return False
    
    async def interactive_mode(self):
        """Interactive testing mode."""
        print(f"\n{Fore.CYAN}{'='*70}")
        print(f"INTERACTIVE MODE")
        print(f"{'='*70}{Style.RESET_ALL}")
        print(f"Type your commands to test. Type 'quit' or 'exit' to stop.\n")
        print(f"{Fore.YELLOW}Special commands:")
        print(f"  - 'stats': Show current pass/fail statistics")
        print(f"  - 'clear': Clear statistics")
        print(f"  - 'help': Show this help{Style.RESET_ALL}\n")
        
        while True:
            try:
                user_input = input(f"{Fore.GREEN}You: {Style.RESET_ALL}")
                
                if user_input.lower() in ['quit', 'exit', 'q']:
                    print(f"\n{Fore.YELLOW}Goodbye!{Style.RESET_ALL}\n")
                    break
                
                if user_input.lower() == 'stats':
                    total = self.passed + self.failed
                    if total > 0:
                        print(f"\n{Fore.CYAN}Statistics:{Style.RESET_ALL}")
                        print(f"  Passed: {self.passed}/{total} ({self.passed/total*100:.1f}%)")
                        print(f"  Failed: {self.failed}/{total} ({self.failed/total*100:.1f}%)\n")
                    else:
                        print(f"\n{Fore.YELLOW}No tests run yet{Style.RESET_ALL}\n")
                    continue
                
                if user_input.lower() == 'clear':
                    self.passed = 0
                    self.failed = 0
                    self.test_results = []
                    print(f"\n{Fore.GREEN}Statistics cleared{Style.RESET_ALL}\n")
                    continue
                
                if not user_input.strip():
                    continue
                
                print(f"{Fore.MAGENTA}Adjnt:{Style.RESET_ALL}")
                await self.test_single(user_input)
                print()
                
            except KeyboardInterrupt:
                print(f"\n\n{Fore.YELLOW}Interrupted. Goodbye!{Style.RESET_ALL}\n")
                break
            except Exception as e:
                print(f"{Fore.RED}Error: {e}{Style.RESET_ALL}\n")

async def main():
    """Main entry point."""
    print(f"\n{Fore.CYAN}╔{'═'*68}╗")
    print(f"║{' '*20}ADJNT LOCAL TESTER{' '*30}║")
    print(f"╚{'═'*68}╝{Style.RESET_ALL}\n")
    
    tester = LocalTester()
    
    # Show menu
    print("Choose mode:")
    print("  1. Run automated tests")
    print("  2. Interactive mode")
    print("  3. Both (automated first, then interactive)")
    print("  4. Quick test (just critical features)\n")
    
    try:
        choice = input("Enter choice (1/2/3/4): ").strip()
        
        if choice == "1":
            await tester.run_all_tests()
        elif choice == "2":
            await tester.interactive_mode()
        elif choice == "3":
            await tester.run_all_tests()
            print(f"\n{Fore.CYAN}Entering interactive mode...{Style.RESET_ALL}")
            await tester.interactive_mode()
        elif choice == "4":
            # Quick test - just test one of each intent type
            quick_tests = [
                TEST_CASES[0],  # TASK
                TEST_CASES[7],  # DELETE - clear store
                TEST_CASES[11], # MOVE - plural
                TEST_CASES[17], # REMIND - Saturday (no time)
                TEST_CASES[21], # DELETE_REMINDERS
                TEST_CASES[24], # UPDATE_REMINDER
                TEST_CASES[28], # LIST
                TEST_CASES[31], # LIST_REMINDERS
                TEST_CASES[34], # TIME
            ]
            print(f"\n{Fore.CYAN}{'='*70}")
            print(f"RUNNING QUICK TEST (KEY FEATURES)")
            print(f"{'='*70}{Style.RESET_ALL}\n")
            
            for idx, test in enumerate(quick_tests, 1):
                print(f"\n{Fore.BLUE}[Test {idx}/{len(quick_tests)}]{Style.RESET_ALL} {test['description']}")
                print(f"{Fore.WHITE}Input: \"{test['input']}\"{Style.RESET_ALL}")
                await tester.test_single(test['input'], test['expected_intent'], test['description'])
                print()
            
            tester._print_summary()
        else:
            print(f"{Fore.RED}Invalid choice. Running automated tests...{Style.RESET_ALL}\n")
            await tester.run_all_tests()
    
    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}Interrupted. Goodbye!{Style.RESET_ALL}\n")

if __name__ == "__main__":
    # Check if colorama is installed
    try:
        import colorama
    except ImportError:
        print("Installing colorama for colored output...")
        import subprocess
        subprocess.check_call(["pip", "install", "colorama"])
        from colorama import init, Fore, Style
        init(autoreset=True)
    
    # Run main
    asyncio.run(main())