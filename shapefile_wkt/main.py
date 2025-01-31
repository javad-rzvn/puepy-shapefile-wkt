import io
import csv
import zipfile
from puepy import Application, Page, t
from puepy.router import Router
from puepy.runtime import is_server_side, add_event_listener
import geopandas as gpd
import pandas as pd
from shapefile_wkt.database import Database


class ShapefileWKT(Application):
    def initial(self):
        return {
            "loading": True,
        }

    def reload_db(self, save=True):
        # self.state["known_people"] = (db.expense.get_unique_names(),)
        # self.state["expenses"] = db.expense.select()
        # self.state["summary"] = db.expense.summary()
        self.state["file_uploaded"] = False
        self.state["loading"] = False
        if save:
            self.local_storage["db"] = db.to_string()


app = ShapefileWKT()
existing_data = app.local_storage.get("db")
db = Database(existing_data)
app.reload_db(save=False)
app.install_router(Router, link_mode=Router.LINK_MODE_HASH)
app.local_storage.get("db")


@app.page("/")
class DefaultPage(Page):
    default_classes = ["flex", "flex-col", "flex-grow"]
    th_classes = "py-2 px-4 font-medium text-gray-500 uppercase tracking-wider"
    td_classes = "py-2 px-4 text-gray-700"

    def initial(self):
        return {"import_error": None, "import_message": None}

    def populate(self):
        if self.application.state["loading"]:
            with t.div(
                style="text-align: center; height: 100vh; display: flex; justify-content: center; align-items: center;"
            ):
                t.sl_spinner(style="font-size: 50px; --track-width: 10px;")
        else:
            with t.header(
                classes="flex justify-between items-center bg-white p-4 mb-4 shadow-lg"
            ):
                t.h1(
                    "Shapefile-WKT",
                    classes="text-4xl font-bold",
                    style="color: rgb(149 96 40)",
                )

            with t.main(classes="flex-grow container mx-auto p-4"):
                with t.div(classes="container mx-auto"):
                    with t.form(on_submit=self.on_import_zip, ref="import_form"):
                        t.input(
                            type="file",
                            label="Select Zip file",
                            ref="import_zip",
                            classes="p-4",
                        )
                    # if self.state["import_error"]:
                    #     with t.sl_alert(open=True, variant="danger"):
                    #         t.sl_icon(name="exclamation-triangle")
                    #         t(self.state["import_error"])
                    t.sl_button(
                        "Import",
                        ref="import_submit",
                        slot="footer",
                        type="submit",
                        variant="primary",
                        on_click=self.on_import_zip,
                    )

                    t.sl_button(
                        "Clear",
                        slot="trigger",
                        variant="warning",
                        on_click=self.on_clear_submit,
                    )

                    print(self.application.state["file_uploaded"])

                    if self.application.state["file_uploaded"]:
                        file_byte_content = self.application.state["file_bytes"]
                        _df = gpd.read_file(file_byte_content)
                        with t.table(classes="table-auto w-full"):
                            t.thead(
                                t.tr(
                                    t.th("OBJECTID_1", classes=self.th_classes),
                                    t.th("NAME", classes=self.th_classes),
                                    t.th("ST_CODE", classes=self.th_classes),
                                    t.th("Shape_Leng", classes=self.th_classes),
                                    t.th("Shape_Area", classes=self.th_classes),
                                ),
                            )
                            with t.tbody():
                                for index, row in _df.iterrows():
                                    t.tr(
                                        t.td(str(row["OBJECTID_1"]), classes=self.td_classes),
                                        t.td(str(row["NAME"]), classes=self.td_classes),
                                        t.td(str(row["ST_CODE"]), classes=self.td_classes),
                                        t.td(str(row["Shape_Leng"]), classes=self.td_classes),
                                        t.td(str(row["Shape_Area"]), classes=self.td_classes),
                                    )

        # self.populate_import_dialog()

    def on_close_import_dialog_click(self, event):
        event.preventDefault()
        self.refs["import_dialog"].element.hide()

    async def on_import_submit(self, event):
        event.preventDefault()
        with self.state.mutate():  # Wait on any changes till after we're done
            self.state["import_error"] = None
            self.state["import_message"] = None
            event.preventDefault()
            file = self.refs["import_file"].element.files.item(0)
            if not file:
                # self.state["import_error"] = "No file selected"
                return
            ab = await file.arrayBuffer()
            fd = io.StringIO(ab.to_bytes().decode("utf-8"))
            reader = csv.DictReader(fd)
            db.conn.execute("BEGIN TRANSACTION;")
            if self.refs["erase"].element.checked:
                db.conn.execute("DELETE FROM expense;")
            for i, row in enumerate(reader):
                try:
                    db.expense.insert_expense(
                        amount=float(row["amount"]),
                        description=row["description"],
                        owed_to=row["owed_to"],
                        owed_from=row["owed_from"],
                        date_created=row["date_created"],
                    )
                except KeyError:
                    self.state["import_error"] = (
                        f"Error on row {i + 1}: Columns do not match expected columns"
                    )
                    db.conn.rollback()
                    return
                except (ValueError, TypeError):
                    self.state["import_error"] = (
                        f"Error on row {i + 1}: Invalid data in row"
                    )
                    db.conn.rollback()
                    return
            self.application.reload_db()
            self.state["import_message"] = "Import successful"
            # self.refs["import_dialog"].element.hide()

    def on_clear_submit(self, event):
        event.preventDefault()
        self.application.reload_db()
        # self.application.state["file_uploaded"] = False
        # self.state["file_bytes"] = io.BytesIO()

    async def on_import_zip(self, event):
        event.preventDefault()
        with self.state.mutate():  # Wait on any changes till after we're done
            self.state["import_error"] = None
            self.state["import_message"] = None
            event.preventDefault()
            file = self.refs["import_zip"].element.files.item(0)
            if not file:
                # self.state["import_error"] = "No file selected"
                return
            ab = await file.arrayBuffer()
            fd = io.BytesIO(ab.to_bytes())
            self.application.state["file_uploaded"] = True
            self.application.state["file_bytes"] = fd
            # try:
            #     print(fd)
            #     df = gpd.read_file(fd)  # Read file as GeoDataFrame
            #     df = df.reset_index(drop=True)
            #     print(df.head())  # Print some data for debugging
            # except Exception as e:
            #     print(f"Error reading file: {e}")

    ##
    ## Import dialog and events
    ##
    def populate_import_dialog(self):
        with t.sl_dialog(ref="import_dialog", label="Import CSV"):
            if self.state["import_message"]:
                with t.sl_alert(open=True):
                    t.sl_icon(name="info-circle")
                    t(" ", self.state["import_message"])
            else:
                t(
                    "This will import a CSV file of your expenses. The file should have columns for owed_from, owed_to,"
                    " description, amount, and date_created."
                )
                with t.form(on_submit=self.on_import_submit, ref="import_form"):
                    t.input(
                        type="file",
                        label="Select CSV file",
                        ref="import_file",
                        classes="p-4",
                    )
                    t.sl_checkbox("Clear existing data", ref="erase")
                if self.state["import_error"]:
                    with t.sl_alert(open=True, variant="danger"):
                        t.sl_icon(name="exclamation-triangle")
                        t(self.state["import_error"])
                t.sl_button(
                    "Import",
                    ref="import_submit",
                    slot="footer",
                    type="submit",
                    variant="primary",
                    on_click=self.on_import_submit,
                )
            t.sl_button(
                "Close",
                ref="import_close",
                slot="footer",
                variant="text",
                on_click=self.on_close_import_dialog_click,
            )


# class HelloWorldPage(Page):
#     def populate(self):
#         t.h1("Hello, World!")


app.mount("#app")
