import "./globals.css";
import type { Metadata } from "next";
import { Inter } from "next/font/google";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
	title: "Musse AI",
	description: "Musse AI",
};

export default function RootLayout({
	children,
}: {
	children: React.ReactNode;
}) {
	return (
		<html lang="en" className="h-full">
			<head>
				{process.env.ENV_NAME == 'prod' ?
					<meta http-equiv="Content-Security-Policy" content="upgrade-insecure-requests" />
					: ""}
					<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.4/css/all.min.css" />
			</head>
			<body className={`${inter.className} h-full`}>
				<div
					className="flex flex-col h-full md:p-8 bg-[#131318]"
				>
					{children}
				</div>
			</body>
		</html>
	);
}
