from typing import List


class FinalQuery:
    def __init__(self, query):
        self._query = query


class Query:
    def __init__(self, query: str, columns: List[str]):
        self.query = query
        self.columns = columns

    def select(self, *columns: str):
        if not (set(columns) <= set(self.columns)):
            raise ValueError(
                f"Unknown column names passed: {set(columns) - set(self.columns)}"
            )

        selected_columns = ", ".join(columns)
        return FinalQuery(f"SELECT {selected_columns} FROM {self.query}")

    def select_star(self):
        return FinalQuery(f"SELECT * FROM {self.query}")

    def where(self, where_clause: str):
        return Query(
            f"{self.query} WHERE {where_clause}",
            columns=self.columns,
        )

    def insert_into(self) -> FinalQuery:
        columns = ", ".join(self.columns)
        placeholders = ", ".join(["?"] * len(self.columns))
        return FinalQuery(
            f"INSERT INTO {self.query}({columns}) VALUES ({placeholders})"
        )

    def drop_table(self) -> FinalQuery:
        return FinalQuery(f"DROP TABLE {self.query}")

    def delete_from(self) -> FinalQuery:
        return FinalQuery(f"DELETE FROM {self.query}")


class Name:
    table_name = "names"
    columns = [
        "name",
        "module",
        "package",
        "source",
        "type",
    ]

    @classmethod
    def create_table(self, connection):
        names_table = (
            "(name TEXT, module TEXT, package TEXT, source INTEGER, type INTEGER)"
        )
        connection.execute(f"CREATE TABLE IF NOT EXISTS names{names_table}")
        connection.execute("CREATE INDEX IF NOT EXISTS name ON names(name)")
        connection.execute("CREATE INDEX IF NOT EXISTS module ON names(module)")
        connection.execute("CREATE INDEX IF NOT EXISTS package ON names(package)")

    objects = Query(table_name, columns)

    search_submodule_like = objects.where('module LIKE ("%." || ?)')
    search_module_like = objects.where("module LIKE (?)")

    import_assist = objects.where("name LIKE (? || '%')")

    search_by_name_like = objects.where("name LIKE (?)")

    delete_by_module_name = objects.where("module = ?").delete_from()


class Package:
    table_name = "packages"
    columns = [
        "package",
        "path",
    ]

    @classmethod
    def create_table(self, connection):
        packages_table = "(package TEXT, path TEXT)"
        connection.execute(f"CREATE TABLE IF NOT EXISTS packages{packages_table}")

    objects = Query(table_name, columns)

    delete_by_package_name = objects.where("package = ?").delete_from()
