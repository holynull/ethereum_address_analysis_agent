"use client";

import { v4 as uuidv4 } from "uuid";
import { ChatWindow } from "../app/components/ChatWindow";
import { ToastContainer } from "react-toastify";

import { ChakraProvider } from "@chakra-ui/react";
import ErrorBoundary from './components/ErrorBoundary';

export default function Home() {
	return (
		<ChakraProvider>
			<ToastContainer />
			<ErrorBoundary>
				<ChatWindow conversationId={uuidv4()}></ChatWindow>
			</ErrorBoundary>
		</ChakraProvider>
	);
}
