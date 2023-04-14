import collections
import json
import copy
import sys
from typing import TypedDict, Callable
import requests
from rich.console import Console
from rich.markdown import Markdown
from rich.pretty import pprint
from deep_compare import deep_compare

# This Class serves two methods for requesting data from https://restcountries.com
# - get_all()
# - get _specific()
class API:
	def __init__(self, route, data_file) -> None:
		self.route = route
		self.data_file = data_file
		self.all_data = None
	
	# TODO: enclose everything in try-except
	def get_all(self, param: str = "") -> object|None:
		try: 
			return json.load(open(self.data_file))
		except:
			if self.all_data: return self.all_data
			
			response = requests.get(self.route + param)

			if response.ok: 
				try:
					self.all_data = response.json()
					new_file = open("all_countries.json", "w")
					new_file.write(json.dumps(self.all_data))
					new_file.close()
				except Exception as e:
					print(Exception)
					print("There was an error writing response response to all_countries.json file.")
				finally:
					self.all_data = response.json()
					return self.all_data
			else:
				print(response.text)
				return None
		# FIXME: make api call when no local file for country	
		# TODO: write files when response.ok
	def get_specific(self, parameter_name: str, parameter_value: str) -> object|None:
		try:
			if parameter_name == "name":
				file = open(f"countries/{parameter_value.split('?')[0]}.json")
				return {"message": "OK", "status": 200, "data": json.load(file) }
			try:
				response = requests.get(f"{self.route}/{parameter_name}/{parameter_value}", timeout=10)

				if response.ok:
					data = response.json()

					for country in data:
						new_file = open(f"{country['name']}.json", "w")
						new_file.write(json.dumps(data))
						new_file.close()

					return {"message": "OK", "status": 200, "data": data}
				raise ValueError(response)
				
			except Exception as e: 
				print(e)
				return {"message": "Not Found", "status": 404, "data": None}
		except Exception as e:
			print(e)
			return {"message": "Couldn't retrieve data!", "status": 500, "data": None}
		
# Type for storing content displayed on console screen
class Page(TypedDict):
	name: str
	message: str 
	options: list[str]|dict

# This class is wholly responsible for representing data in the console and handling user navigation
class Navigate:
	current: Page
	home: Page
	previous: collections.deque[Page] = collections.deque()
	basic_instructions = "Enter **b** to go back, **h** to go to main screen, or **q** to exit to program."
	fetch_error_message = "There was a problem retreiving the necessary response!\nEnter **r** to retry."
	all_countries = []

	# 1
	def __init__(self) -> None:
		# home page contents
		self.home: Page = {
			"name": "home",
			"message": open("./home.md").read(), 
			"options": ["List all countries", "Search for a specific country"]
		}
		self.current = self.home
		# console API for printing markdown
		self.console = Console()
		self.go_home()

	# 2
	def go_home(self) -> None:
		self.previous.clear() # clear previous pages list
		self.current = copy.deepcopy(self.home)
		self.print_page()
		user_choice = self.get_user_choice()
		
		if user_choice == 1:
			self.list_all()
		else: self.search_specific()

	# 3
	def go_back(self, retry_callback) -> None:
		self.current = copy.deepcopy(self.previous.pop())
		
		match self.current["name"]:
			case "home": return self.go_home()
			case "list_all": return self.list_all(True)
			case "search_specific": return self.search_specific(True)
			case _: return retry_callback(True)

	# 4
	def append_to_previous(self, was_revisited: bool) -> bool:
		# Check if it was called directly from home
		was_not_called_again = (len(self.previous) and deep_compare(self.previous[-1], self.current)) == False

		if was_not_called_again and not was_revisited:
			self.previous.append(copy.deepcopy(self.current))
			return True
		
		return False

	# 5
	def handle_no_data(self, response: object, current_page_name: str, retry_callback: Callable) -> None:
		self.current = {
				"name":	current_page_name,
				"message": response["message"],
				"options": None
				}
		self.console.print(Markdown(self.fetch_error_message))
		self.print_instructions(self.basic_instructions)
		
		return self.get_user_choice(str, retry_callback)

	# 6
	def list_all(self, was_revisited: bool = False) -> None:
		self.append_to_previous(was_revisited)

		response = CountriesAPI.get_all("/all")

		if response == None: 
			return self.handle_no_data(response, "list_all", self.list_all)

		self.all_countries.clear()
		for item in response:
			self.all_countries.append(item["name"]["common"])

		self.all_countries.sort()
		self.current: Page = {
			"name": "list_all",
			"message": "Below is the list of countries that exist today in the world.\nTo retreive information about a country, enter its serial number:",
			"options": self.all_countries
		}

		self.print_page()
		print("To retreive information about a country, enter its serial number.")
		# Again print instructions at the bottom of huge countries list
		self.print_instructions(self.basic_instructions)
		
		user_choice = self.get_user_choice()
		target_country = self.all_countries[user_choice - 1]

		self.list_country(["name", f"{target_country}?fullText=true"])

	# 7
	def search_specific(self, was_revisited: bool = False) -> None:
		self.append_to_previous(was_revisited)

		self.current: Page = {
			"name": "search_specific",
			"message": "Choose one of the following options to continue:",
			"options": {
				"name":	"Search by name",
				"alpha":	"Search by country code",
				"capital":	"Search by capital city",
				"currency":	"Search by currency",
				"lang":	"Search by language",
				"region":	"Search by region",
				"subregion":	"Search by subregion",
				"translation":	"Search by translation name",
			}
		}

		self.print_page()
		print("Choose one of the options above to continue:\n")

		user_choice = self.get_user_choice()
		param_name = list(self.current["options"])[user_choice - 1]
		print(f"Please enter the {param_name} for the country you're looking for:")
		param_value = self.get_user_choice(str)
		
		self.list_country([param_name, param_value])
	
	# 8
	def list_country(self, param: list[str], was_revisited: bool = False) -> None:
		self.append_to_previous(was_revisited)
		
		param_name = param[0]
		param_value = param[1]

		response = CountriesAPI.get_specific(param_name, param_value)
		
		if response["data"] == None: 
			def refresh_callback(was_revisited: bool = False):
				return self.list_country(param, was_revisited)
			
			return self.handle_no_data(response, "list_country", refresh_callback)
		
		data: object
		message: str

		if len(response["data"]) > 1:
			data = response["data"]
			message = f"We found {len(response['data'])} results for your query:"
		else:
			data = response["data"][0]
			message = "Alright! Here's everything we know about the country:"
			
		self.current: Page = {
			"name": "list_country",
			"message": message,
			"options": data
		}

		self.print_page(print_ordered_list=False)
		self.print_instructions(self.basic_instructions)
		self.get_user_choice(str)

	# 9
	def print_instructions(self, string) -> None:
		if self.current["name"] != "home":
			# print instructions for 'back' and 'home'
			print("\n")
			self.console.print(Markdown(string))
			print("\n")

	def print_page(self, print_ordered_list: bool = True) -> None:
		self.print_instructions(self.basic_instructions)

		# print current page message & options
		if self.current['message']:
			self.console.print(Markdown(self.current['message']))
			print("\n")

		# List available options
		try:
			if print_ordered_list:
				options_list = self.current['options']

				if type(options_list) == dict:
					options_list = list(options_list)
					index = 1
					for item in options_list:
						print(f"{index}. {self.current['options'][item]}.\n")
						index += 1
						
				else:
					for i in range(0, len(options_list)):
						print(f"{i + 1}. {options_list[i]}.\n")
					
			# List country details
			else:
				pprint(self.current['options'])
		except:
			raise ValueError("There was a problem while printing the object!")

	# 10
	def get_user_choice(self, choice_type=int, retry_callback=None):
		user_input  = input(": ")


		if self.current["name"] != "home":
			match user_input:
				case 'r': 
					if retry_callback: 
						return retry_callback(True)
					else:
						return self.get_user_choice()
					
				case 'b':
					self.go_back(retry_callback)
					return None
				case 'h':
					self.go_home()
					return None
		
		if user_input == 'q':
			self.console.print(Markdown("*See you soon!*"))
			sys.exit()
				
		if choice_type == int:
			integer = None
			try: 
				integer = int(user_input)
			except: 
				print(f"Please enter a number between 1 and {len(self.current['options'])}!")
				return self.get_user_choice(choice_type)
			else:
				if integer > 0 and integer <= len(self.current['options']): 
					return int(user_input)
				print(f"Please enter a number between 1 and {len(self.current['options'])}!")
				return self.get_user_choice()
			
		elif choice_type == str and self.current["name"] == "search_specific":
			return user_input
			
		else:
			print("Please enter a valid choice:\n")
			return self.get_user_choice(choice_type, retry_callback)


# Initialize API and Call Navigate() to run the program
CountriesAPI = API("https://restcountries.com/v3.1", "all_countries.json")
Navigate()