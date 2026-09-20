import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "VendorSphere SLMCT",
  description: "Subscription, licences, and cost tracking for VendorSphere group operations.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
