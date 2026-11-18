import type { CellValue, DataType } from "@/lib/api";

/**
 * EXAMPLE DATA — not any real business.
 *
 * Small, internally consistent sample tables shown on the "Use sample data" page.
 * They are built from one shared set of products, customers and sales, so totals
 * line up (a sale's total is quantity × price; a customer's "total spent" is the sum
 * of their sales here). Every ID starts with "EX-" and product names start with
 * "Example:", so example rows are recognisable if a person adds them to their account.
 */

export interface SampleColumn {
  key: string;
  label: string;
  meaning: string;
}

export interface Sample {
  id: string;
  type: DataType;
  title: string;
  blurb: string;
  columns: SampleColumn[];
  /** Other kinds of data that must exist first (so a sale can point at a real product). */
  companions: DataType[];
  rows: () => Record<string, CellValue>[];
}

const iso = (daysAgo: number): string => {
  const d = new Date();
  d.setDate(d.getDate() - daysAgo);
  return d.toISOString().slice(0, 10);
};

const PRODUCTS = [
  { id: "EX-P1", name: "Example: Cotton Kurta", category: "Clothing", cost: 380, price: 799, stock: 60 },
  { id: "EX-P2", name: "Example: Linen Shirt", category: "Clothing", cost: 620, price: 1299, stock: 45 },
  { id: "EX-P3", name: "Example: Block-Print Dress", category: "Clothing", cost: 740, price: 1599, stock: 30 },
];
const price = (pid: string) => PRODUCTS.find((p) => p.id === pid)!.price;

// [days ago, product, customer, quantity]
const SALES_RAW: [number, string, string, number][] = [
  [3, "EX-P1", "EX-C1", 2],
  [5, "EX-P2", "EX-C2", 1],
  [8, "EX-P1", "EX-C3", 3],
  [11, "EX-P3", "EX-C1", 1],
  [14, "EX-P1", "EX-C4", 2],
  [18, "EX-P2", "EX-C3", 2],
  [22, "EX-P1", "EX-C2", 1],
  [27, "EX-P3", "EX-C4", 2],
  [36, "EX-P1", "EX-C1", 1],
  [41, "EX-P2", "EX-C2", 1],
  [47, "EX-P3", "EX-C3", 1],
  [55, "EX-P1", "EX-C4", 2],
];

const salesRows = () =>
  SALES_RAW.map(([d, p, c, q]) => ({
    sale_date: iso(d),
    product: p,
    customer: c,
    quantity: q,
    unit_price: price(p),
    discount: 0,
    revenue: q * price(p),
  }));

const customerRows = () =>
  ["EX-C1", "EX-C2", "EX-C3", "EX-C4"].map((cid) => {
    const mine = SALES_RAW.filter((s) => s[2] === cid);
    return {
      external_customer_id: cid,
      segment: mine.length >= 3 ? "Regular" : "New",
      first_purchase_date: iso(Math.max(...mine.map((s) => s[0]))),
      last_purchase_date: iso(Math.min(...mine.map((s) => s[0]))),
      purchase_frequency: mine.length,
      monetary_value: mine.reduce((sum, s) => sum + s[3] * price(s[1]), 0),
    };
  });

export const SAMPLES: Sample[] = [
  {
    id: "sales",
    type: "sales",
    title: "Sales data",
    blurb: "Each row is one sale: when it happened, what was sold, to whom, how many, and the total.",
    companions: ["products", "customers"],
    columns: [
      { key: "sale_date", label: "Date", meaning: "The day the sale happened." },
      { key: "product", label: "Product", meaning: "Which product was sold (its Product ID)." },
      { key: "customer", label: "Customer", meaning: "Who bought it (their Customer ID). Optional." },
      { key: "quantity", label: "Quantity", meaning: "How many units were sold." },
      { key: "unit_price", label: "Price each (₹)", meaning: "The price of one unit." },
      { key: "revenue", label: "Total (₹)", meaning: "Quantity × price, after any discount." },
    ],
    rows: salesRows,
  },
  {
    id: "customers",
    type: "customers",
    title: "Customer data",
    blurb: "Each row is one customer: when they first and last bought, how often, and how much they spent.",
    companions: [],
    columns: [
      { key: "external_customer_id", label: "Customer ID", meaning: "A short code or name for the customer." },
      { key: "segment", label: "Group", meaning: "A label such as New or Regular. Optional." },
      { key: "first_purchase_date", label: "First purchase", meaning: "The day they first bought from you." },
      { key: "last_purchase_date", label: "Last purchase", meaning: "The most recent day they bought." },
      { key: "purchase_frequency", label: "Times bought", meaning: "How many purchases they made." },
      { key: "monetary_value", label: "Total spent (₹)", meaning: "Everything they have spent with you." },
    ],
    rows: customerRows,
  },
  {
    id: "products",
    type: "products",
    title: "Product list",
    blurb: "Each row is something you sell, with its cost, price and how many you have.",
    companions: [],
    columns: [
      { key: "external_product_id", label: "Product ID", meaning: "A short code for the product (SKU)." },
      { key: "name", label: "Name", meaning: "What you call the product." },
      { key: "category", label: "Category", meaning: "A group such as Clothing. Optional." },
      { key: "unit_cost", label: "Cost each (₹)", meaning: "What one unit costs you. Optional." },
      { key: "selling_price", label: "Selling price (₹)", meaning: "What you sell one unit for." },
      { key: "stock_quantity", label: "In stock", meaning: "How many you have right now. Optional." },
    ],
    rows: () =>
      PRODUCTS.map((p) => ({
        external_product_id: p.id,
        name: p.name,
        category: p.category,
        unit_cost: p.cost,
        selling_price: p.price,
        stock_quantity: p.stock,
      })),
  },
  {
    id: "inventory",
    type: "inventory",
    title: "Stock levels",
    blurb: "Each row says how much stock you had of a product on a day, and when you'd want to reorder.",
    companions: ["products"],
    columns: [
      { key: "date", label: "Date", meaning: "The day the stock was counted." },
      { key: "product", label: "Product", meaning: "Which product (its Product ID)." },
      { key: "stock_level", label: "In stock", meaning: "How many units you had." },
      { key: "reorder_level", label: "Reorder at", meaning: "The level at which you'd order more. Optional." },
    ],
    rows: () =>
      PRODUCTS.flatMap((p) => [
        { date: iso(30), product: p.id, stock_level: p.stock + 10, reorder_level: 15 },
        { date: iso(1), product: p.id, stock_level: p.stock, reorder_level: 15 },
      ]),
  },
  {
    id: "finance",
    type: "finance",
    title: "Expenses & profit",
    blurb: "Each row is one month of money figures: what came in, what it cost, and what was left.",
    companions: [],
    columns: [
      { key: "period_date", label: "Month", meaning: "The month these figures are for." },
      { key: "revenue", label: "Income (₹)", meaning: "Total money that came in." },
      { key: "cogs", label: "Cost of goods (₹)", meaning: "What the things you sold cost you." },
      { key: "operating_expenses", label: "Running costs (₹)", meaning: "Rent, salaries, bills and so on." },
      { key: "net_profit", label: "Profit (₹)", meaning: "Income minus both kinds of cost." },
    ],
    rows: () =>
      [
        [90, 180000, 90000, 40000],
        [60, 195000, 96000, 41000],
        [30, 210000, 101000, 41500],
      ].map(([d, rev, cogs, opex]) => ({
        period_date: iso(d),
        revenue: rev,
        cogs,
        operating_expenses: opex,
        net_profit: rev - cogs - opex,
      })),
  },
];

/** Adds the example's companion data first (so links resolve), then the example itself. */
export async function installSample(
  sample: Sample,
  add: (type: DataType, rows: Record<string, CellValue>[]) => Promise<unknown>,
): Promise<void> {
  for (const companion of sample.companions) {
    const c = SAMPLES.find((s) => s.type === companion);
    if (c) await add(c.type, c.rows());
  }
  await add(sample.type, sample.rows());
}

/**
 * What a prepared file should contain, per kind of data. These are exactly the fields the app
 * understands (the same ones as manual entry), with a plausible example value for each.
 * `required` fields must be present for the file to be accepted.
 */
export interface ReferenceField {
  label: string;
  example: string;
  required: boolean;
}

export const REFERENCE_FORMAT: Record<DataType, ReferenceField[]> = {
  sales: [
    { label: "Date", example: "2026-09-14", required: true },
    { label: "Product", example: "Cotton Kurta", required: false },
    { label: "Quantity", example: "2", required: true },
    { label: "Price each", example: "799", required: true },
    { label: "Customer", example: "C-102", required: false },
  ],
  customers: [
    { label: "Customer ID", example: "C-102", required: true },
    { label: "First purchase", example: "2026-03-02", required: false },
    { label: "Last purchase", example: "2026-09-14", required: false },
    { label: "Times bought", example: "4", required: false },
    { label: "Total spent", example: "3200", required: false },
  ],
  products: [
    { label: "Product ID", example: "P-1", required: true },
    { label: "Name", example: "Cotton Kurta", required: true },
    { label: "Selling price", example: "799", required: true },
    { label: "Cost each", example: "380", required: false },
    { label: "In stock", example: "60", required: false },
  ],
  inventory: [
    { label: "Date", example: "2026-09-14", required: true },
    { label: "Product ID", example: "P-1", required: true },
    { label: "In stock", example: "60", required: true },
    { label: "Reorder at", example: "15", required: false },
  ],
  marketing_campaigns: [
    { label: "Date", example: "2026-09-10", required: true },
    { label: "Where (channel)", example: "Instagram", required: true },
    { label: "Spent", example: "5000", required: true },
    { label: "Clicks", example: "340", required: false },
    { label: "Orders", example: "12", required: false },
  ],
  finance: [
    { label: "Month", example: "2026-08-01", required: true },
    { label: "Income", example: "250000", required: false },
    { label: "Cost of goods", example: "110000", required: false },
    { label: "Running costs", example: "60000", required: false },
    { label: "Profit", example: "80000", required: false },
  ],
};
