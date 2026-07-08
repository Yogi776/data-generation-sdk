import {
  Boxes,
  Database,
  FileText,
  FlaskConical,
  Gauge,
  LayoutDashboard,
  Layers,
  Sparkles,
  Table2,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  description: string;
}

export const NAV: NavItem[] = [
  {
    href: "/",
    label: "Overview",
    icon: LayoutDashboard,
    description: "Project status at a glance",
  },
  {
    href: "/sources",
    label: "Sources",
    icon: Database,
    description: "Connected data sources",
  },
  {
    href: "/catalog",
    label: "Catalog",
    icon: Table2,
    description: "Tables, columns & relationships",
  },
  {
    href: "/profile",
    label: "Profiling",
    icon: Gauge,
    description: "Stats, distributions & PII",
  },
  {
    href: "/generate",
    label: "Generate",
    icon: Boxes,
    description: "FK-safe synthetic data",
  },
  {
    href: "/quality",
    label: "Quality",
    icon: FlaskConical,
    description: "Derived checks & score",
  },
  {
    href: "/semantic",
    label: "Semantic",
    icon: Layers,
    description: "Fact/dimension models",
  },
  {
    href: "/sql",
    label: "Ask (SQL)",
    icon: Sparkles,
    description: "Natural language → SQL",
  },
  {
    href: "/docs",
    label: "Data dictionary",
    icon: FileText,
    description: "Generated documentation",
  },
];
