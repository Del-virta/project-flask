import io

from flask import (
    Flask,
    json,
    request,
    redirect,
    url_for,
    jsonify,
    render_template,
    flash,
    send_file,
)
import re
import json
import statistics
from datetime import datetime


class IncorrectInput(Exception):
    pass


class FieldDecodeError(Exception):
    pass


def index_error_decorator(function):
    def inner(*args):
        try:
            result = function(*args)
            return result
        except ValueError:
            raise IncorrectInput(f"Index value is not integer!")

    return inner


class DataField:
    field_description = "General"

    def __init__(self, value):
        self.value = None
        self.validate(value)

    def to_json(self):
        return {"value": self.value, "field_name": self.field_description}

    def validate(self, value):
        self.value = value

    def __contains__(self, item):
        return item in self.value

    def __str__(self):
        return f"{self.field_description}: {self.value}"


class NameField(DataField):
    field_description = "Name"


class NoteField(DataField):
    field_description = "Note"


class BirthdayField(DataField):
    field_description = "Birthday"

    def validate(self, value: str):
        if not datetime.strptime(value, '%d.%m.%Y'):
            raise IncorrectInput(f"{value} is not a date dd.mm.yyy!")
        self.value = value


class PhoneField(DataField):
    field_description = "Phone"
    PHONE_REGEX = re.compile(r"^\+?(\d{2})?\(?(0\d{2})\)?(\d{7}$)")

    def __init__(self, value):
        self.country_code: str = ""
        self.operator_code: str = ""
        self.phone_number: str = ""
        super().__init__(value)

    def validate(self, value: str):
        value = value.replace(" ", "")
        search = re.search(self.PHONE_REGEX, value)
        try:
            country, operator, phone = search.group(1, 2, 3)
        except AttributeError:
            raise IncorrectInput(f"No phone number found in {value}")

        if operator is None:
            raise IncorrectInput(f"Operator code not found in {value}")

        self.country_code = country if country is not None else "38"
        self.operator_code = operator
        self.phone_number = phone
        self.value = f"+{self.country_code}{self.operator_code}{self.phone_number}"


class EmailField(DataField):
    field_description = "Email"
    EMAIL_REGEX = re.compile(r"[^@]+@[^@]+\.[^@]+")

    def validate(self, value: str):
        if not self.EMAIL_REGEX.match(value):
            raise IncorrectInput(f"{value} is not an email.")
        self.value = value


REGISTERED_FIELDS = {
    NameField.field_description: NameField,
    PhoneField.field_description: PhoneField,
    EmailField.field_description: EmailField,
    BirthdayField.field_description: BirthdayField,
    NoteField.field_description: NoteField
}


def field_decoder(field_dict):
    try:
        field_class = REGISTERED_FIELDS[field_dict["field_name"]]
        field = field_class(field_dict["value"])
    except KeyError:
        raise FieldDecodeError(
            "Wrong message format. 'field_name' and 'value' required"
        )
    return field


class Contact:
    def __init__(self):
        self.fields = []
        self.phone = ""
        self.birthday = ""
        self.mail = ""
        self.note = ""

    def __len__(self):
        return len(self.fields)

    def __getitem__(self, key):
        return self.fields[key]

    def __iter__(self):
        return enumerate(self.fields)

    def to_json(self):
        return {"fields": [field.to_json() for field in self.fields]}

    def from_json(self, dict_contact):
        field_list = dict_contact["fields"]
        if field_list:
            for field_dict in field_list:
                field = field_decoder(field_dict)
                self.add(field)

    def get_birthday(self):
        for field in self.fields:
            if field.field_description == "Birthday":
                return field.value

    def get_phone(self):
        phones = []
        for field in self.fields:
            if field.field_description == "Phone":
                phones.append(field.value)
        return "; ".join(phones) if phones else ""

    def name(self):
        names = []
        for field in self.fields:
            if field.field_description == "Name":
                names.append(field.value)
        name = " ".join(names) if names else ""
        result = " ".join(name)
        return result if result != " " else "No name"

    def get_mail(self):
        for field in self.fields:
            if field.field_description == "Email":
                return field.value
        return ""

    def get_note(self):
        for field in self.fields:
            if field.field_description == "Note":
                return field.value
        return ""

    def add(self, field_item):
        self.fields.append(field_item)
        return self.fields.index(field_item)

    @index_error_decorator
    def replace(self, index, field_item):
        self.fields[index] = field_item

    @index_error_decorator
    def delete(self, idx):
        idx = int(idx)
        self.fields.pop(idx)

    @index_error_decorator
    def update(self, field_idx, value):
        field_idx = int(field_idx)
        field = self.fields[field_idx]
        field.validate(value)

    def field_search(self, field_name, search_value):
        for field in self.fields:
            if field.field_description == field_name:
                return search_value in field
        return False

    def multiple_search(self, **search_items):
        for field_name, search_value in search_items.items():
            current_search = self.field_search(field_name, search_value)
            if not current_search:
                return False
        return True

    def __contains__(self, item: str):
        for field in self.fields:
            if item in field:
                return True
        return False

    def __str__(self) -> str:
        return self.name()


class AddressBook:
    def __init__(self):
        self.contacts = {}
        self.last_contact_id = 0

    def __getitem__(self, key):
        return self.contacts[key]

    def dumps(self):
        contacts = {rec_id: rec.to_json() for rec_id, rec in self.contacts.items()}
        return json.dumps(contacts)

    def loads(self, bytes_contacts): #Достать из файла и сделать объектом
        self.contacts.clear()
        self.last_contacts_id = 0
        json_contacts = json.loads(bytes_contacts)
        for _, contact_list in json_contacts.items():
            contact = Contact()
            contact.from_json(contact_list)
            self.add(contact)
        

    def add(self, contact):  # Добавить элемент
        self.contacts[self.last_contact_id] = contact
        contact_id = self.last_contact_id
        self.last_contact_id += 1
        return contact_id

    def replace(self, contact_id, contact):   #Заменить
        if contact_id not in self.contacts:
            raise KeyError(f"contact {contact_id} not found")
        self.contacts[contact_id] = contact

    @index_error_decorator
    def delete(self, contact_id):   #Удалить
        key = int(contact_id)
        self.contacts.pop(key)

    def str_search(self, search_str: str):   #поиск строки
        result = {}
        for contact_id, contact in self.contacts.items():
            if search_str in contact:
                result[contact_id] = contact
        return result

    def multiple_search(self, **search_items): # множественный поиск (убрать, т.к. указатели)
        result = {}
        for contact_id, contact in self.contacts.items():
            if contact.multiple_search(**search_items):
                result[contact_id] = contact
        return result

    def clear(self):    #очистить
        self.contacts.clear()
        self.last_contact_id = 0


app = Flask("answer")
AB = AddressBook()

with open("ab.json") as file:
    AB.loads(file.read())


@app.errorhandler(KeyError)
def handle_contact_not_found(_):
    return render_template("error.jinja", message="Record not found")


@app.errorhandler(IndexError)
def handle_field_not_found(_):
    return render_template("error.jinja", message="Field not found")


@app.errorhandler(IncorrectInput)
def handle_invalid_input(error):
    return render_template("error.jinja", message=str(error))


@app.errorhandler(FieldDecodeError)
def handle_invalid_format(error):
    return render_template("error.jinja", message=str(error))


@app.route("/")
def ab():
    return render_template(
        "contacts.jinja", contacts=AB.contacts, stat_url=''
    )



@app.route("/dump")
def ab_dump():
    fh = io.BytesIO(AB.dumps().encode())
    return send_file(fh, attachment_filename="AB.json")


@app.route("/clear")
def ab_clear():
    AB.clear()
    return redirect(url_for("ab"))


@app.route("/load", methods=("GET", "POST"))
def ab_load():
    if request.method == "POST":
        if "file" not in request.files:
            flash("No file part")
            return redirect(request.url)
        file = request.files["file"]
        if file.filename == "":
            flash("No selected file")
            return redirect(request.url)
        AB.loads(file.stream.read())
        return redirect(url_for("ab"))
    return render_template("load.jinja")


@app.route("/search", methods=("GET", "POST"))
def search():
    if request.method == "GET":
        return render_template("search.jinja", fields=REGISTERED_FIELDS.keys())

    if request.form["value"] != "":
        #stat_url = url_for("search_stat", all=request.form["value"])
        search_result = AB.str_search(request.form["value"])
    else:
        fields = [field for field in request.form.to_dict(flat=False)["field"]]
        values = [value for value in request.form.to_dict(flat=False)["value"]]
        search_query = {
            field: value for field, value in filter(lambda x: x[1], zip(fields, values))
        }
        print(search_query)
        #stat_url = url_for("search_stat", **search_query)
        search_result = AB.multiple_search(**search_query)
    return render_template("contacts.jinja", contacts=search_result, stat_url='')


@app.route("/ab/contact", methods=("GET", "POST"))
def new_contact():
    contact = Contact()
    contact_id = AB.add(contact)
    return redirect(url_for(endpoint="contact", contact_id=contact_id))


@app.route("/ab/contact/<int:contact_id>/delete")
def delete_contact(contact_id):
    AB.delete(contact_id)
    return redirect(url_for(endpoint="ab", contact_id=contact_id))


@app.route("/ab/contact/<int:contact_id>", methods=("GET", "POST"))
def contact(contact_id):
    current_contact = AB[contact_id]
    if request.method == "POST":
        if "idx" in request.form:
            idxs = [int(idx) for idx in request.form.to_dict(flat=False)["idx"]]
            types = [f_type for f_type in request.form.to_dict(flat=False)["type"]]
            values = [value for value in request.form.to_dict(flat=False)["value"]]
            for idx, f_type, value in zip(idxs, types, values):
                current_contact.update(idx, value)
        else:
            field_class = REGISTERED_FIELDS[request.form["type"]]
            field = field_class(request.form["value"])
            current_contact.add(field)

    return render_template(
        "contact.jinja",
        contact=current_contact,
        contact_id=contact_id,
        fields=REGISTERED_FIELDS.keys(),
    )


@app.route("/ab/contact/<int:contact_id>/field/<int:field_index>/delete")
def delete_field(contact_id, field_index):
    current_contact = AB[contact_id]
    current_contact.delete(field_index)
    return redirect(url_for("contact", contact_id=contact_id))


def main():
    from werkzeug.serving import run_simple

    run_simple("0.0.0.0", 5050, app)


if __name__ == "__main__":
    main()
