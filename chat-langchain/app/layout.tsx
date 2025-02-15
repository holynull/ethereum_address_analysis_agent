import "./globals.css";
import type { Metadata } from "next";
import { Inter } from "next/font/google";

import { AppKit } from './context/appkit'
import { headers } from 'next/headers'


const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
	title: "Musse AI",
	description: "Musse AI",
};
// app/layout.tsx
// export const dynamic = 'auto'
// 或者
// export const dynamic = 'force-dynamic'
// 添加这行来启用动态渲染
// 添加以下配置
// export const runtime = 'edge' // 'nodejs' or 'edge'
// export const dynamic = 'force-dynamic'
// export const revalidate = 0
// export const fetchCache = 'force-no-store'
export default function RootLayout({
	children,
}: {
	children: React.ReactNode;
}) {
	// 获取cookies
	// const headersObj = await headers();
	// const cookies = headersObj.get('cookie')
	return (
		<html lang="en" className="h-full">
			<head>
				{process.env.ENV_NAME == 'prod' ?
					<meta http-equiv="Content-Security-Policy" content="upgrade-insecure-requests" />
					: ""}
				<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.4/css/all.min.css" />
			</head>
			<body className={`${inter.className} h-full`}>
				<AppKit cookies={null}>
					<div
						className="flex flex-col h-full md:p-8 bg-[#131318]"
					>
						{children}
					</div></AppKit>
			</body>
		</html>
	);
}
