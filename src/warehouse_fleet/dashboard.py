"""Unified 6-tab Tkinter Dashboard for Warehouse Robot Fleet Telemetry."""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk

from PIL import Image, ImageTk

from warehouse_fleet.config import DatabaseConfig
from warehouse_fleet.controller import FleetDashboardController
from warehouse_fleet.db import create_fleet_engine, init_schema, seed_demo_data
from warehouse_fleet.queries import QueryResult


def _populate_treeview(tree: ttk.Treeview, result: QueryResult) -> None:
    tree.delete(*tree.get_children())
    tree["columns"] = result.columns
    tree["show"] = "headings"
    for col in result.columns:
        tree.heading(col, text=col)
        tree.column(col, width=130, anchor="w", stretch=True)
    for row in result.rows:
        display_vals = ["None" if v is None else str(v) for v in row]
        tree.insert("", "end", values=display_vals)


class WarehouseFleetApp(ttk.Frame):
    """6-tab Tkinter UI bound to FleetDashboardController."""

    def __init__(
        self,
        master: tk.Misc,
        controller: FleetDashboardController,
    ) -> None:
        super().__init__(master, padding=10)
        self.master = master
        self.controller = controller
        self._current_photo: ImageTk.PhotoImage | None = None
        self._last_query_result: QueryResult = QueryResult(columns=[], rows=[])
        self._preset_map = {p.label: p.preset_id for p in self.controller.list_presets()}

        self.status_var = tk.StringVar(master=self, value="Query rows: 0")
        self.datalog_robot_var = tk.StringVar(master=self, value="ALL")
        self.route_table_var = tk.StringVar(master=self, value="RouteLog")
        self.preset_label_var = tk.StringVar(
            master=self,
            value=self.controller.list_presets()[0].label,
        )
        self.query_robot_var = tk.StringVar(master=self, value="R1")
        self.query_date_var = tk.StringVar(master=self, value="2025-09-01")
        self.import_table_var = tk.StringVar(master=self, value="RobotRoute_raw")
        self.image_status_var = tk.StringVar(
            master=self, value="Select an ImageData row and click View Image."
        )

        self.pack(fill="both", expand=True)
        self._build_ui()
        self.refresh_all()

    def _build_ui(self) -> None:
        header = ttk.Frame(self)
        header.pack(fill="x", pady=(0, 8))
        ttk.Label(
            header,
            text="Warehouse Robot Fleet Telemetry Dashboard",
            font=("Segoe UI", 13, "bold"),
        ).pack(side="left")
        ttk.Label(header, textvariable=self.status_var).pack(side="right")

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True)

        self._build_robots_tab()
        self._build_sensors_tab()
        self._build_datalogs_tab()
        self._build_routes_tab()
        self._build_analytics_tab()
        self._build_images_tab()

    def _build_robots_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=8)
        self.notebook.add(tab, text="Robots")

        controls = ttk.Frame(tab)
        controls.pack(fill="x", pady=(0, 6))
        ttk.Button(controls, text="Reload", command=self.refresh_robots).pack(side="right", padx=4)
        ttk.Button(
            controls,
            text="Export CSV",
            command=lambda: self._export_table_dialog("Robot"),
        ).pack(side="right")

        self.robots_tree = ttk.Treeview(tab)
        self.robots_tree.pack(fill="both", expand=True)

    def _build_sensors_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=8)
        self.notebook.add(tab, text="Sensors")

        controls = ttk.Frame(tab)
        controls.pack(fill="x", pady=(0, 6))
        ttk.Button(controls, text="Reload", command=self.refresh_sensors).pack(side="right", padx=4)
        ttk.Button(
            controls,
            text="Simulate MQTT Sample",
            command=self._on_simulate_mqtt,
        ).pack(side="right", padx=4)

        ttk.Label(tab, text="Registered Sensors (Sensor)").pack(anchor="w")
        self.sensors_tree = ttk.Treeview(tab, height=6)
        self.sensors_tree.pack(fill="both", expand=True, pady=(2, 8))

        ttk.Label(tab, text="ESP32 MQTT Telemetry Stream (SensorLog)").pack(anchor="w")
        self.sensorlog_tree = ttk.Treeview(tab, height=8)
        self.sensorlog_tree.pack(fill="both", expand=True, pady=(2, 0))

    def _build_datalogs_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=8)
        self.notebook.add(tab, text="DataLogs")

        controls = ttk.Frame(tab)
        controls.pack(fill="x", pady=(0, 6))
        ttk.Label(controls, text="Robot:").pack(side="left")
        combo = ttk.Combobox(
            controls,
            textvariable=self.datalog_robot_var,
            values=("ALL", "R1", "R2", "R3", "R4"),
            state="readonly",
            width=8,
        )
        combo.pack(side="left", padx=6)
        combo.bind("<<ComboboxSelected>>", lambda _e: self.refresh_datalogs())

        ttk.Button(controls, text="Reload", command=self.refresh_datalogs).pack(side="right", padx=4)
        ttk.Button(
            controls,
            text="Export CSV",
            command=lambda: self._export_table_dialog("DataLog"),
        ).pack(side="right")

        self.datalogs_tree = ttk.Treeview(tab)
        self.datalogs_tree.pack(fill="both", expand=True)

    def _build_routes_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=8)
        self.notebook.add(tab, text="RouteLog / MoveLog")

        controls = ttk.Frame(tab)
        controls.pack(fill="x", pady=(0, 6))
        ttk.Label(controls, text="Table:").pack(side="left")
        combo = ttk.Combobox(
            controls,
            textvariable=self.route_table_var,
            values=("RouteLog", "RobotRoute_raw", "RobotMoveLog"),
            state="readonly",
            width=18,
        )
        combo.pack(side="left", padx=6)
        combo.bind("<<ComboboxSelected>>", lambda _e: self.refresh_routes())

        ttk.Button(controls, text="Seed R1 (3NF)", command=self._on_seed_routelog).pack(
            side="left", padx=6
        )
        ttk.Button(controls, text="Reload", command=self.refresh_routes).pack(side="right", padx=4)
        ttk.Button(
            controls,
            text="Export CSV",
            command=lambda: self._export_table_dialog(self.route_table_var.get()),
        ).pack(side="right")

        self.routes_tree = ttk.Treeview(tab)
        self.routes_tree.pack(fill="both", expand=True)

    def _build_analytics_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=8)
        self.notebook.add(tab, text="Analytics & Queries")

        query_bar = ttk.Frame(tab)
        query_bar.pack(fill="x", pady=(0, 6))
        ttk.Label(query_bar, text="Preset:").pack(side="left")
        ttk.Combobox(
            query_bar,
            textvariable=self.preset_label_var,
            values=tuple(self._preset_map.keys()),
            state="readonly",
            width=34,
        ).pack(side="left", padx=6)
        ttk.Label(query_bar, text="Robot:").pack(side="left")
        ttk.Entry(query_bar, textvariable=self.query_robot_var, width=8).pack(side="left", padx=4)
        ttk.Label(query_bar, text="Date:").pack(side="left")
        ttk.Entry(query_bar, textvariable=self.query_date_var, width=12).pack(side="left", padx=4)
        ttk.Button(query_bar, text="Run", command=self.run_selected_preset).pack(side="left", padx=4)
        ttk.Button(query_bar, text="Export CSV", command=self._export_query_dialog).pack(
            side="right"
        )

        io_bar = ttk.Frame(tab)
        io_bar.pack(fill="x", pady=(0, 6))
        ttk.Label(io_bar, text="Import Table:").pack(side="left")
        ttk.Combobox(
            io_bar,
            textvariable=self.import_table_var,
            values=tuple(self.controller.list_tables()),
            state="readonly",
            width=20,
        ).pack(side="left", padx=6)
        ttk.Button(io_bar, text="Import CSV", command=self._import_csv_dialog).pack(side="left")

        self.analytics_tree = ttk.Treeview(tab)
        self.analytics_tree.pack(fill="both", expand=True)

    def _build_images_tab(self) -> None:
        tab = ttk.Frame(self.notebook, padding=8)
        self.notebook.add(tab, text="Image Viewer")

        controls = ttk.Frame(tab)
        controls.pack(fill="x", pady=(0, 6))
        ttk.Button(controls, text="View Image", command=self.view_selected_image).pack(side="left")
        ttk.Button(controls, text="Reload", command=self.refresh_images).pack(side="right")
        ttk.Label(controls, textvariable=self.image_status_var).pack(side="left", padx=12)

        pane = ttk.PanedWindow(tab, orient="horizontal")
        pane.pack(fill="both", expand=True)

        self.images_tree = ttk.Treeview(pane)
        pane.add(self.images_tree, weight=1)

        preview_frame = ttk.Frame(pane, padding=8)
        pane.add(preview_frame, weight=1)
        self.image_preview_label = ttk.Label(preview_frame, text="No image loaded", anchor="center")
        self.image_preview_label.pack(fill="both", expand=True)

    def refresh_all(self) -> None:
        self.refresh_robots()
        self.refresh_sensors()
        self.refresh_datalogs()
        self.refresh_routes()
        self.refresh_images()
        self.run_selected_preset()

    def refresh_robots(self) -> None:
        _populate_treeview(self.robots_tree, self.controller.fetch_table("Robot", limit=None))

    def refresh_sensors(self) -> None:
        _populate_treeview(self.sensors_tree, self.controller.fetch_table("Sensor", limit=None))
        _populate_treeview(self.sensorlog_tree, self.controller.fetch_table("SensorLog", limit=None))

    def refresh_datalogs(self) -> None:
        robot = self.datalog_robot_var.get()
        rid = None if robot == "ALL" else robot
        _populate_treeview(
            self.datalogs_tree,
            self.controller.fetch_table("DataLog", limit=None, robot_id=rid),
        )

    def refresh_routes(self) -> None:
        table = self.route_table_var.get()
        _populate_treeview(self.routes_tree, self.controller.fetch_table(table, limit=None))

    def refresh_images(self) -> None:
        _populate_treeview(self.images_tree, self.controller.fetch_table("ImageData", limit=None))

    def run_selected_preset(self) -> None:
        try:
            label = self.preset_label_var.get()
            preset_id = self._preset_map[label]
            res = self.controller.run_preset(
                preset_id,
                robot_id=self.query_robot_var.get().strip() or "R1",
                target_date=self.query_date_var.get().strip() or "2025-09-01",
            )
            self._last_query_result = res
            _populate_treeview(self.analytics_tree, res)
            self.status_var.set(f"Query rows: {len(res.rows)}")
        except Exception as exc:
            self.status_var.set(f"Error: {exc}")

    def _on_simulate_mqtt(self) -> None:
        try:
            inserted = self.controller.simulate_mqtt_sample(
                robot_id=self.query_robot_var.get().strip() or "R1"
            )
            self.refresh_sensors()
            self.status_var.set(f"Simulated MQTT rows ingested: {inserted}")
        except Exception as exc:
            self.status_var.set(f"Error: {exc}")

    def _on_seed_routelog(self) -> None:
        try:
            count = self.controller.seed_routelog_r1(
                day=self.query_date_var.get().strip() or "2025-09-01",
                robot_id=self.query_robot_var.get().strip() or "R1",
            )
            self.route_table_var.set("RouteLog")
            self.refresh_routes()
            self.status_var.set(f"Seeded RouteLog rows: {count}")
        except Exception as exc:
            self.status_var.set(f"Error: {exc}")

    def display_image_path(self, img_path: str) -> bool:
        try:
            pil_img = self.controller.load_image(img_path)
            pil_img.thumbnail((420, 320), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(pil_img, master=self)
        except (FileNotFoundError, ValueError, OSError) as exc:
            self._current_photo = None
            self.image_preview_label.configure(image="", text=f"Unable to load image: {exc}")
            self.image_status_var.set(f"Error: {exc}")
            return False

        self._current_photo = photo
        self.image_preview_label.configure(image=photo, text="")
        self.image_status_var.set(f"Loaded: {img_path}")
        return True

    def view_selected_image(self) -> bool:
        selection = self.images_tree.selection()
        if not selection:
            children = self.images_tree.get_children()
            if not children:
                self.image_status_var.set("No ImageData rows available.")
                return False
            item_id = children[0]
        else:
            item_id = selection[0]
        values = self.images_tree.item(item_id, "values")
        columns = list(self.images_tree["columns"])
        if "img_path" in columns:
            path_idx = columns.index("img_path")
        elif len(values) >= 3:
            path_idx = 2
        else:
            self.image_status_var.set("Selected row has no img_path column.")
            return False
        if path_idx >= len(values):
            self.image_status_var.set("Selected row has no img_path column.")
            return False
        return self.display_image_path(str(values[path_idx]))

    def _export_table_dialog(self, table_name: str) -> None:
        out_file = filedialog.asksaveasfilename(
            parent=self,
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            initialfile=f"{table_name}.csv",
        )
        if out_file:
            try:
                res = self.controller.fetch_table(table_name, limit=None)
                self.controller.export_csv(res, Path(out_file))
                self.status_var.set(f"Exported {len(res.rows)} rows to {Path(out_file).name}")
            except Exception as exc:
                self.status_var.set(f"Error: {exc}")

    def _export_query_dialog(self) -> None:
        out_file = filedialog.asksaveasfilename(
            parent=self,
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            initialfile="query_results.csv",
        )
        if out_file:
            try:
                self.controller.export_csv(self._last_query_result, Path(out_file))
                self.status_var.set(
                    f"Exported {len(self._last_query_result.rows)} query rows to {Path(out_file).name}"
                )
            except Exception as exc:
                self.status_var.set(f"Error: {exc}")

    def _import_csv_dialog(self) -> None:
        in_file = filedialog.askopenfilename(
            parent=self,
            filetypes=[("CSV files", "*.csv")],
        )
        if in_file:
            try:
                table = self.import_table_var.get()
                count = self.controller.import_csv(table, Path(in_file))
                self.refresh_all()
                self.status_var.set(f"Imported {count} rows into {table}")
            except Exception as exc:
                self.status_var.set(f"Error: {exc}")


def launch_dashboard(
    db_url: str | None = None,
    base_dir: Path | str | None = None,
) -> None:
    """Create schema/seed if empty and launch the Tkinter WarehouseFleetApp."""
    repo_root = Path(base_dir).resolve() if base_dir is not None else Path.cwd().resolve()
    engine = create_fleet_engine(db_url=db_url, config=DatabaseConfig.from_env())
    init_schema(engine)
    data_dir = repo_root / "data"
    seed_demo_data(engine, data_dir=data_dir if data_dir.exists() else None)
    controller = FleetDashboardController(engine, base_dir=repo_root)

    root = tk.Tk()
    root.title("Warehouse Robot Fleet Telemetry")
    root.geometry("1100x700")
    WarehouseFleetApp(root, controller)
    root.mainloop()
