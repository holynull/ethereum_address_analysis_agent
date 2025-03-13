"use client";

import { Text, Tooltip } from "@chakra-ui/react";
import React, { useEffect, useRef, useState, useCallback } from "react";
import { ethers } from "ethers";
import { useSearchParams } from "next/navigation";
import { RemoteRunnable } from "langchain/runnables/remote";

import { ChatMessageBubble, Message, TxData } from "../components/ChatMessageBubble";
import { AutoResizeTextarea } from "./AutoResizeTextarea";
import { marked } from "marked";
import { Renderer } from "marked";
import hljs from "highlight.js";
import "highlight.js/styles/gradient-dark.css";

import "react-toastify/dist/ReactToastify.css";
import {
	Heading,
	Flex,
	IconButton,
	InputGroup,
	InputRightElement,
	Spinner,
	Box,
	ButtonGroup
} from "@chakra-ui/react";
import { ArrowUpIcon, CloseIcon, Icon, SmallCloseIcon } from "@chakra-ui/icons";
import { Select } from "@chakra-ui/react";
import { Source } from "./SourceBubble";
import { AIMessageChunk, ToolMessage } from "@langchain/core/messages"
import { FaCircleNotch, FaTools, FaKeyboard, FaCheck, FaLightbulb, FaPlus, FaWallet } from 'react-icons/fa';

import {
	UploadedImageFile,
	UploadedImageUrl,
	UploadedPDFFile
} from '../types/file';
import FileUploadArea from './FileUploadArea';
import GlobalPasteHint from './GlobalPasteHint';
import { mainnet, bsc, tron, optimism, arbitrum, sepolia, polygon, solana } from '@reown/appkit/networks'
import { useAppKit, useAppKitProvider, useAppKitAccount, useAppKitNetwork, useAppKitState, useAppKitEvents, useWalletInfo } from "@reown/appkit/react"
import { useAppKitConnection } from '@reown/appkit-adapter-solana/react'
import { wcModal } from "../context/appkit"


enum ProcessingStatus {
	Idle = "idle",
	SynthesizingQuestion = "synthesizing_question",
	InvokingTool = "invoking_tool",
	Processing = "processing",
	Typing = "typing",
	Completed = "completed"
}

export function ChatWindow(props: { conversationId: string }) {
	const conversationId = props.conversationId;

	const searchParams = useSearchParams();

	const messageContainerRef = useRef<HTMLDivElement | null>(null);
	const [messages, setMessages] = useState<Array<Message>>([]);
	const [activeConnector, setActiveConnector] = useState<'metamask' | 'walletconnect' | null>(null);
	const [network, setNetwork] = useState<string>("");
	// const [isConnected, setIsConnected] = useState(false);
	const [input, setInput] = useState("");
	const [showUpload, setShowUpload] = useState(false);
	const [imageFiles, setImageFiles] = useState<UploadedImageFile[]>([]);
	const [imageUrls, setImageUrls] = useState<UploadedImageUrl[]>([]);
	const [pdfFiles, setPdfFiles] = useState<UploadedPDFFile[]>([]);




	const openFileUpload = () => {
		if (!showUpload) {
			setShowUpload(prev => !prev);
			console.log("show upload:" + showUpload)
		}
	};

	const [isLoading, setIsLoading] = useState(false);
	const [abortController, setAbortController] = useState<AbortController | null>(null);
	const [llm, setLlm] = useState(
		searchParams.get("llm") ?? "anthropic_claude_3_5_sonnet",
	);

	const [chatHistory, setChatHistory] = useState<
		{ type: string; content: string }[]
	>([]);

	const [processingStatus, setProcessingStatus] = useState<ProcessingStatus>(ProcessingStatus.Idle);

	const handleCancel = useCallback(async () => {
		if (abortController && !abortController.signal.aborted) {
			try {
				await Promise.race([
					// 将 abort() 包装在 Promise.resolve 中
					Promise.resolve(abortController.abort()),
					new Promise((resolve) => setTimeout(resolve, 1000))
				]);
			} catch (e) {
				if (e === 'AbortError') {
					return;
				}
				console.error(e);
			} finally {
				// 清理状态
				setAbortController(null);
				setIsLoading(false);
				setProcessingStatus(ProcessingStatus.Idle);
			}
		}
	}, [abortController]);
	useEffect(() => {
		return () => {
			if (abortController && !abortController.signal.aborted) {
				abortController.abort("CLEANUP");
			}
		};
	}, [abortController]);

	function showProcessingStatus(status: ProcessingStatus) {
		switch (status) {
			case ProcessingStatus.Idle:
				return null;
			case ProcessingStatus.SynthesizingQuestion:
				return (
					<div className="flex items-center text-blue-500">
						<FaCircleNotch className="animate-spin mr-2" size={20} />
						<span>Thinking</span>
					</div>
				);
			case ProcessingStatus.InvokingTool:
				return (
					<div className="flex items-center text-purple-500">
						<FaTools className="mr-2" size={20} />
						<span>Using Tools</span>
					</div>
				);
			case ProcessingStatus.Processing:
				return (
					<div className="flex items-center text-orange-500">
						<FaCircleNotch className="animate-spin mr-2" size={20} />
						<span>Processing</span>
					</div>
				);
			case ProcessingStatus.Typing:
				return (
					<div className="flex items-center text-green-500">
						<FaKeyboard className="mr-2" size={20} />
						<span>Typing</span>
					</div>
				);
			case ProcessingStatus.Completed:
				return (
					<div className="flex items-center text-green-500">
						<FaCheck className="mr-2" size={20} />
						<span>Completed</span>
					</div>
				);
		}
	}

	// Check if device is mobile
	const isMobile = () => {
		if (typeof window !== 'undefined') {
			return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
		}
		return false
	};

	// Load WalletConnect session from localStorage
	const loadWcSession = () => {
		try {
			const savedSession = localStorage.getItem('walletconnect_session');
			if (savedSession) {
				return JSON.parse(savedSession);
			}
		} catch (error) {
			console.error('Error loading WalletConnect session:', error);
		}
		return null;
	};

	// Walletconnect AppKit
	const { open, close } = useAppKit();
	const { address, isConnected, caipAddress, status, embeddedWalletInfo } = useAppKitAccount()
	const { caipNetwork, caipNetworkId, chainId, switchNetwork } = useAppKitNetwork()
	// const { open, selectedNetworkId } = useAppKitState()
	const events = useAppKitEvents()
	// const { walletProvider_solana } = useAppKitProvider<Provider>('solana') as any
	// const { solanaProvider } = useAppKitProvider('solana')
	const { walletInfo } = useWalletInfo()
	const { connection } = useAppKitConnection()
	const [txDataEvm, setTxDataEvm] = useState<any>(null)
	const [txDataSol, setTxDataSol] = useState<any>(null)
	const [txDataSolTW, setTxDataSolTW] = useState<any>(null)
	const [isShowSendEvmTx, setShowSendEvmTx] = useState<boolean>(false)
	const [isShowSendSolTx, setShowSendSolTx] = useState<boolean>(false)
	const [isShowSendSolTxTW, setShowSendSolTxTW] = useState<boolean>(false)
	const connectWallet = async () => {
		await open({ view: "Connect" })
	}

	const CHAIN_CONFIG = {
		"ethereum": {
			"network": mainnet,
		},
		"bsc": {
			"network": bsc
		},
		"polygon": {
			"network": polygon,
		},
		"arbitrum": {
			"network": arbitrum,
		},
		"optimism": {
			"network": optimism,
		},
		"solana": {
			"network": solana,
		},
		"tron": {
			"network": tron
		}
	}

	const _change_network_to = async (chainId: string) => {
		const chainData = CHAIN_CONFIG[chainId as keyof typeof CHAIN_CONFIG] as any;
		wcModal.switchNetwork(chainData.network)
		switchNetwork(chainData.network)
	}
	const change_network_to = async (network_data: any) => {
		if (Array.isArray(network_data) && network_data.length >= 2) {
			const chainId = network_data[1].network_name;
			await _change_network_to(chainId)
		}
	}

	const sendMessage = async (message?: string) => {
		if (messageContainerRef.current) {
			messageContainerRef.current.classList.add("grow");
		}
		if (isLoading) {
			return;
		}
		const messageValue = message ?? input;
		if (messageValue === "") return;
		setInput("");

		// 收集当前所有图片
		const currentImages = [
			...imageFiles.map(img => img.base64),
			...imageUrls.map(img => img.base64),
		].filter(Boolean);

		const currentPDFs = pdfFiles.map(pdf => pdf.base64).filter(Boolean);

		setMessages((prevMessages) => {
			const newMessages = [
				...prevMessages,
				{
					id: Math.random().toString(),
					content: messageValue,
					role: "user" as const, // 明确指定类型
					images: currentImages,
					txDatas: []
				} as Message
			];
			setTimeout(scrollToBottom, 0);
			return newMessages;
		});
		setIsLoading(true);
		const controller = new AbortController();
		setAbortController(controller);


		let accumulatedMessage = "";
		let runId: string | undefined = undefined;
		let sources: Source[] | undefined = undefined;
		let messageIndex: number | null = null;

		const markdownStyles = {
			code: `
			  background-color: #1e1e2e;
			  color: #cdd6f4;
			  padding: 0.2em 0.4em;
			  border-radius: 3px;
			  font-size: 0.9em;
			  font-family: 'Fira Code', monospace;
			`,
			pre: `
			  background-color: #1e1e2e;
			  padding: 1em;
			  border-radius: 8px;
			  overflow-x: auto;
			  margin: 1em 0;
			  border: 1px solid #313244;
			`,
			blockquote: `
			  border-left: 4px solid #7f849c;
			  margin: 1em 0;
			  padding: 0.5em 1em;
			  background-color: #27273a;
			  border-radius: 4px;
			`,
			table: `
			  width: 100%;
			  border-collapse: collapse;
			  margin: 1em 0;
			`,
			th: `
			  background-color: #313244;
			  padding: 0.75em;
			  border: 1px solid #45475a;
			  text-align: left;
			`,
			td: `
			  padding: 0.75em;
			  border: 1px solid #45475a;
			`,
			link: `
			  color: #89b4fa;
			  text-decoration: none;
			  &:hover {
				text-decoration: underline;
			  }
			`,
			list: `
			  padding-left: 1.5em;
			  margin: 0.5em 0;
			`,
			listItem: `
			  margin: 0.3em 0;
			`,
		};
		let renderer = new Renderer();

		renderer.code = (code, language) => {
			const validLanguage = hljs.getLanguage(language || "")
				? language
				: "plaintext";
			const highlightedCode = hljs.highlight(
				validLanguage || "plaintext",
				code,
			).value;
			return `<pre class="highlight bg-gray-700" style="padding: 5px; border-radius: 5px; overflow: auto; overflow-wrap: anywhere; white-space: pre-wrap; max-width: 100%; display: block; line-height: 1.2"><code class="${language}" style="color: #d6e2ef; font-size: 12px; ">${highlightedCode}</code></pre>`;
		};

		renderer.blockquote = (quote) => {
			return `<blockquote style="${markdownStyles.blockquote}">${quote}</blockquote>`;
		};

		renderer.table = (header, body) => {
			return `<table style="${markdownStyles.table}">
			  <thead>${header}</thead>
			  <tbody>${body}</tbody>
			</table>`;
		};

		renderer.tablerow = (content) => {
			return `<tr>${content}</tr>`;
		};

		renderer.tablecell = (content, flags) => {
			const type = flags.header ? 'th' : 'td';
			const style = flags.header ? markdownStyles.th : markdownStyles.td;
			return `<${type} style="${style}">${content}</${type}>`;
		};

		renderer.link = (href, title, text) => {
			return `<a href="${href}" title="${title || ''}" 
			  style="${markdownStyles.link}" 
			  target="_blank" 
			  rel="noopener noreferrer">${text}</a>`;
		};

		renderer.list = (body, ordered) => {
			const type = ordered ? 'ol' : 'ul';
			return `<${type} style="${markdownStyles.list}">${body}</${type}>`;
		};

		renderer.listitem = (text) => {
			return `<li style="${markdownStyles.listItem}">${text}</li>`;
		};
		renderer.html = (html) => {
			console.log(html)
			// 这里可以添加一些验证逻辑，例如只允许特定的 iframe
			// if (html.startsWith('<iframe') && html.includes('musse.ai')) {
			// return html;
			// }
			// 对于其他 HTML，你可以选择返回空字符串、原始 HTML 或经过转义的 HTML
			return html; // 或者 return html; 或者 return marked.escapeHtml(html);
		};
		// 设置 marked 选项
		marked.setOptions({
			renderer,
			highlight: function (code, language) {
				if (language && hljs.getLanguage(language)) {
					try {
						return hljs.highlight(code, {
							language: language,
							ignoreIllegals: true
						}).value;
					} catch (err) {
						console.error(err);
						return code;
					}
				}
				return code;
			},
			pedantic: false,
			gfm: true,
			breaks: true,
			sanitize: false,
			smartLists: true,
			smartypants: false,
			xhtml: false
		});

		try {
			const remoteChain = new RemoteRunnable({
				url: process.env.NEXT_PUBLIC_CHAT_URL ? process.env.NEXT_PUBLIC_CHAT_URL : "",
				options: {
					timeout: 3000000,
				},
			});
			const llmDisplayName = llm ?? "openai_gpt_3_5_turbo";
			let streams = await remoteChain.stream(
				{
					messages: [{ "type": "human", "content": messageValue }],
					wallet_address: address ? address : "",
					chain_id: chainId ? chainId.toString() : "-1",
					wallet_is_connected: isConnected,
					llm: llmDisplayName,
					// chat_history: chatHistory,
					chat_history: [],
					image_urls: currentImages,
					pdf_files: currentPDFs,
				},
				{
					configurable: {
						llm: llmDisplayName,
						thread_id: conversationId,
					},
					tags: ["model:" + llmDisplayName],
					metadata: {
						conversation_id: conversationId,
						llm: llmDisplayName,
						is_multimodal: currentImages.length > 0 || currentPDFs.length > 0, // 当有图片时为 true
						images_size: currentImages.length,
					},
					signal: controller.signal
				},
				// {
				//   includeNames: [sourceStepName],
				// },
			);
			for await (const chunk of streams) {
				console.log(chunk)
				var _chunk: object
				if (typeof chunk === "object") {
					_chunk = chunk as object;
					if ("run_id" in _chunk) {
						runId = _chunk.run_id as string;
					}
					var kind = "event" in _chunk ? _chunk.event : "";
					switch (kind) {
						case "on_chain_start":
							setProcessingStatus(ProcessingStatus.SynthesizingQuestion);
							break;
						case "on_chain_end":
							setProcessingStatus(ProcessingStatus.Processing);
							break;
						case "on_chain_stream":
							break
						case "on_chat_model_start":
							setProcessingStatus(ProcessingStatus.Processing);
							break;
						case "on_chat_model_end":
							setProcessingStatus(ProcessingStatus.Completed);
							break;
						case "on_chat_model_stream":
							setProcessingStatus(ProcessingStatus.Typing);
							if ("data" in _chunk) {
								var data = _chunk.data as object
								if ("chunk" in data && data.chunk instanceof AIMessageChunk) {
									var aichunk = data.chunk as AIMessageChunk;
									if (typeof (aichunk.content) == "string")
										accumulatedMessage += aichunk.content.toString();
									else if (Array.isArray(aichunk.content) && aichunk.content[0] && "text" in aichunk.content[0]) {
										var c_t = aichunk.content[0]['text'] as string;
										accumulatedMessage += c_t;
									}
									else {
										// console.log(_chunk)
									}
								}
							}
							var parsedResult = marked.parse(accumulatedMessage);
							if (parsedResult != undefined) {
								setMessages((prevMessages) => {
									let newMessages = [...prevMessages];
									if (
										messageIndex === null ||
										newMessages[messageIndex] === undefined
									) {
										messageIndex = newMessages.length;
										newMessages.push({
											id: Math.random().toString(),
											content: parsedResult.trim(),
											runId: runId,
											sources: sources,
											role: "assistant",
										});
									} else if (newMessages[messageIndex] !== undefined) {
										newMessages[messageIndex].content = parsedResult.trim();
										newMessages[messageIndex].runId = runId;
										// newMessages[messageIndex].txDatas = [];
										// newMessages[messageIndex].sources = sources;
									}
									// 使用 setTimeout 确保在 DOM 更新后执行滚动
									setTimeout(scrollToBottom, 0);
									return newMessages;
								});
							}
							break
						case "on_tool_start":
							setProcessingStatus(ProcessingStatus.InvokingTool);

							break;
						case "on_tool_end":
							setProcessingStatus(ProcessingStatus.Processing);
							// if ("name" in _chunk && _chunk.name == "googleSerperSearch") {
							// 	if ("data" in _chunk) {
							// 		var data = _chunk.data as object;
							// 		if ("output" in data) {
							// 			var output = eval('(' + data.output + ')');
							// 			sources = output.map((doc: Record<string, any>) => ({
							// 				url: doc.link,
							// 				title: doc.title,
							// 			}));
							// 		}
							// 	}
							// }
							let currentSources: Source[] = [];
							if ("name" in _chunk && _chunk.name == 'search') {
								if ("data" in _chunk) {
									var data = _chunk.data as object;
									if ("output" in data) {
										let message = data.output as ToolMessage;
										let result = JSON.parse(message.content as string);
										var _output = result;//data.output as Array<any>
										currentSources = _output.map((doc: Record<string, any>) => ({
											url: doc.value.url,
											title: doc.value.title,
											img_src: doc.value.imageUrl,
										}));
									}
								}
							}
							if ("name" in _chunk && (_chunk.name == "searchWebPageToAnswer" || _chunk.name == "searchNewsToAnswer")) {
								if ("data" in _chunk) {
									var data = _chunk.data as object;
									if ("output" in data) {
										let message = data.output as ToolMessage;
										let result = JSON.parse(message.content as string);
										var output = result;//eval('(' + data.output + ')') as object;
										if ("search_result" in output) {
											var search_result = output.search_result as Array<any>
											currentSources = search_result.map((doc: Record<string, any>) => ({
												url: doc.link,
												title: doc.title,
												img_src: doc.imageUrl,
											}));
										}
									}
								}
							}
							if ("name" in _chunk && (_chunk.name == "gen_images" || _chunk.name == "generate_social_media_image")) {
								if ("data" in _chunk) {
									var data = _chunk.data as object;
									if ("output" in data) {
										let message = data.output as ToolMessage;
										let result = JSON.parse(message.content as string);
										// 处理生成的图片数据
										const generatedImages = result as string[];
										const imageMarkdowns = generatedImages.map(url => `${url}\n`);
										accumulatedMessage += imageMarkdowns.join('');
									}
								}
							}
							if ("name" in _chunk && (_chunk.name == "get_balances_of_address"
								|| _chunk.name == "get_token_balance_daily_of_address"
								|| _chunk.name == "get_addres_funds_movements_of")) {
								if ("data" in _chunk) {
									var data = _chunk.data as object;
									if ("output" in data) {
										// 处理生成的图片数据
										let message = data.output as ToolMessage;
										let results = JSON.parse(message.content as string) as [];
										// const results = data.output as string[];
										const func_return = results.map(r => `${r}\n`);
										let return_str = ""
										if (func_return.length > 1) {
											return_str = func_return[1]
										}
										accumulatedMessage += return_str;
									}
								}
							}
							if ("name" in _chunk && _chunk.name == "connect_to_wallet") {
								if ("data" in _chunk) {
									var data = _chunk.data as object;
									if ("output" in data) {
										let message = data.output as ToolMessage;
										let result = JSON.parse(message.content as string);
										await connectWallet();
										// await connect_solana_wallet();
										// todo: use walletconnect appkit to impletment connect wallet
									}
								}
							}
							if ("name" in _chunk && _chunk.name == "change_network_to") {
								if ("data" in _chunk) {
									var data = _chunk.data as object;
									if ("output" in data) {
										let message = data.output as ToolMessage;
										let result = JSON.parse(message.content as string);
										change_network_to(result)
									}
								}
							}
							// if ("name" in _chunk && _chunk.name == "change_account") {
							// 	if ("data" in _chunk) {
							// 		var data = _chunk.data as object;
							// 		if ("output" in data) {
							// 			const result = data.output as any;
							// 			try {
							// 				if (typeof window.ethereum !== 'undefined') {
							// 					const accounts = await window.ethereum.request({
							// 						method: 'eth_requestAccounts'
							// 					});
							// 					if (accounts && accounts.length > 0 && result && result.accountIndex < accounts.length) {
							// 						const newAccount = accounts[result.accountIndex];
							// 						setAccount(newAccount);
							// 						setIsConnected(true);
							// 					}
							// 				}
							// 			} catch (error) {
							// 				console.error('Error changing account:', error);
							// 			}
							// 		}
							// 	}
							let chainType: "evm" | "sol" | "tron" | undefined = undefined;
							let txData: any = null;
							let txName: string = '';
							if ("name" in _chunk && (_chunk.name == "generate_transfer_native_token" || _chunk.name == "generate_approve_erc20" || _chunk.name == "generate_approve_trc20" || _chunk.name == "generate_transfer_erc20_tx_data")) {
								if ("data" in _chunk) {
									var data = _chunk.data as object;
									if ("output" in data) {
										let message = data.output as ToolMessage;
										let result = JSON.parse(message.content as string);
										if (Array.isArray(result) && result.length >= 2) {
											txData = result[1] as any;
											if (txData["chain_id"] != chainId && txData['chain_id'] !== 'tron') {
												await _change_network_to(txData["chain_id"])
											}
											// setTxDataEvm(txData);
											// setShowSendEvmTx(true);
											chainType = 'evm';
											txData = txData;
											txName = txData['name']
										}
									}
								}
							}
							let orderInfo: any = null;
							if ("name" in _chunk && (_chunk.name == "generate_swap_tx_data")) {
								if ("data" in _chunk) {
									var data = _chunk.data as object;
									if ("output" in data) {
										let message = data.output as ToolMessage;
										let result = JSON.parse(message.content as string);
										if (Array.isArray(result) && result.length >= 2) {
											result = result[1] as any;
											if (result["success"]) {
												orderInfo = result.order_info;
												const swap_data = result["swap_data"] as any;
												if (!swap_data.chain_type) {
													throw new Error("Missing chain_type in swap data");
												}
												let signedTx = null;
												if (swap_data.chain_type === "evm") {
													// setTxDataEvm(swap_data.txData)
													// setShowSendEvmTx(true)
													chainType = 'evm'
												} else if (swap_data.chain_type === "solana") {
													if (!connection) {
														wcModal.switchNetwork(solana)
														// open({ view: "Connect" })
													}
													// setTxDataSol(txData)
													// setShowSendSolTx(true)
													chainType = 'sol'
													// if (walletInfo?.name === "Trust Wallet") {
													// setTxDataSol(null)
													// setShowSendSolTx(false)
													// setTxDataSolTW(txData)
													// setShowSendSolTxTW(true)
													// }
												} else if (swap_data.chain_type === "tron") {
													if (!connection) {
														wcModal.switchNetwork(solana)
														// open({ view: "Connect" })
													}
													// setTxDataSol(txData)
													// setShowSendSolTx(true)
													chainType = 'tron'
													// if (walletInfo?.name === "Trust Wallet") {
													// setTxDataSol(null)
													// setShowSendSolTx(false)
													// setTxDataSolTW(txData)
													// setShowSendSolTxTW(true)
													// }

												} else {
													console.error('Unsupported chain type:', swap_data.chain_type);
													accumulatedMessage += `\nUnsupported chain type: ${swap_data.chain_type}`;
												}
												txData = swap_data.txData
												txName = swap_data.name
											}
										}
									}
								}
							}

							sources = [...sources ? sources : [], ...currentSources];
							setMessages((prevMessages) => {
								let newMessages = [...prevMessages];
								if (
									messageIndex === null ||
									newMessages[messageIndex] === undefined
								) {
									messageIndex = newMessages.length;
									newMessages.push({
										id: Math.random().toString(),
										content: parsedResult ? parsedResult.trim() : "",
										runId: runId,
										sources: sources,
										role: "assistant",
										txDatas: {
											chainType: chainType,
											txData: txData,
											txName: txName,
											orderInfo: orderInfo,
										}

									});
								} else if (newMessages[messageIndex] !== undefined) {
									// newMessages[messageIndex].content = parsedResult.trim();
									newMessages[messageIndex].runId = runId;
									newMessages[messageIndex].sources = sources;
									if (chainType && txData) {
										if (!newMessages[messageIndex].txDatas) {
											newMessages[messageIndex].txDatas = {
												chainType: chainType,
												txData: txData,
												txName: txName,
												orderInfo: orderInfo,
											}
										}
										chainType = undefined;
										txData = null;
									}
								}
								// 使用 setTimeout 确保在 DOM 更新后执行滚动
								setTimeout(scrollToBottom, 0);
								return newMessages;
							});
							break
						default:
							break
					}
				}
			}
			setChatHistory((prevChatHistory) => [
				...prevChatHistory,
				{ type: "human", content: messageValue },
				{ type: "ai", content: accumulatedMessage },
			]);
			setIsLoading(false);
			setAbortController(null);
			setProcessingStatus(ProcessingStatus.Idle);
		} catch (e) {
			// setMessages((prevMessages) => prevMessages.slice(0, -1));
			setIsLoading(false);
			setAbortController(null);
			setInput(messageValue);
			setProcessingStatus(ProcessingStatus.Idle);
			throw e;
		}


	};

	const insertUrlParam = (key: string, value?: string) => {
		if (window.history.pushState) {
			const searchParams = new URLSearchParams(window.location.search);
			searchParams.set(key, value ?? "");
			const newurl =
				window.location.protocol +
				"//" +
				window.location.host +
				window.location.pathname +
				"?" +
				searchParams.toString();
			window.history.pushState({ path: newurl }, "", newurl);
		}
	};
	const scrollToBottom = () => {
		if (messageContainerRef.current) {
			messageContainerRef.current.scrollTop = messageContainerRef.current.scrollHeight;
		}
	};
	// Check wallet connection status on component mount
	const checkWalletConnection = async () => {
		if (typeof window.ethereum !== 'undefined') {
			try {
				// Get current accounts
				const accounts = await window.ethereum.request({ method: 'eth_accounts' });
				if (accounts && accounts.length > 0) {
					// setAccount(accounts[0]);
					// setIsConnected(true);

					// // Get current network
					// const provider = new ethers.providers.Web3Provider(window.ethereum as ExternalProvider);
					// const network = await provider.getNetwork();
					// const chainId = network.chainId.toString();
					// setChainId(chainId);
					// setNetwork(network.name);
				}
			} catch (error) {
				console.error('Error checking wallet connection:', error);
			}
		}
	};

	useEffect(() => {
		scrollToBottom();
	}, [messages]);

	// 处理关闭提示的函数
	const handleClosePasteHint = () => {
		setShowPasteHint(false);
	};

	// 添加状态控制提示的显示
	const [showPasteHint, setShowPasteHint] = useState(true);
	// 组件挂载时启动定时器，几秒后隐藏提示
	useEffect(() => {
		const timer = setTimeout(() => {
			setShowPasteHint(false);
		}, 8000); // 8秒后自动隐藏

		return () => clearTimeout(timer);
	}, []);

	return (
		<div className="min-h-screen w-full bg-[#131318]">
			{/* {showPasteHint && <GlobalPasteHint onClose={handleClosePasteHint} />} */}
			<div className="flex flex-col min-h-screen w-full bg-[#131318] overflow-x-hidden">
				<div className="flex flex-col items-center p-4 md:p-8 pb-16 grow w-full max-w-[1200px] mx-auto">
					<Flex
						direction={"column"}
						alignItems={"center"}
						marginTop={messages.length > 0 ? "2" : "8"}
						mb={6}
						position="sticky"
						top={0}
						bg="rgba(19, 19, 24, 0.95)"
						backdropFilter="blur(8px)"
						zIndex={10}
						width="100%"
						py={4}
					>
						<Heading
							fontSize={messages.length > 0 ? "2xl" : "3xl"}
							fontWeight={"medium"}
							mb={2}
							color={"white"}
							textAlign="center"
						>
							<Box position="absolute" right="4" top="4">
								<Tooltip
									label={isConnected ?
										`Connected via ${activeConnector === 'metamask' ? 'MetaMask' : 'WalletConnect'}: ${network} (Chain ID: ${chainId}) - ${address}` :
										'Connect Wallet'}
									placement="top">
									{isConnected ? (
										<IconButton
											colorScheme="green"
											rounded={"full"}
											aria-label="Disconnect Wallet"
											icon={<Icon as={FaWallet} />}
											onClick={async () => { await open({ view: "Account" }) }}
										/>
									) : (
										<IconButton
											colorScheme="red"
											rounded={"full"}
											aria-label="Connect MetaMask"
											icon={<Icon as={FaWallet} />}
											onClick={async () => { await connectWallet() }}
										/>
									)}
								</Tooltip>
							</Box>
							Ξ Musse AI Assistant 💼
						</Heading>
						{isMobile() && isConnected && (
							<div className="text-white text-sm mt-2 text-center px-4">
								<div>Network: {network} (Chain ID: {chainId})</div>
								<div className="mt-1 opacity-80 break-all">{address}</div>
							</div>
						)}
						<Heading
							fontSize="xl"
							fontWeight={"normal"}
							color={"white"}
							marginTop={"10px"}
							textAlign={"center"}
						>
							Ask me anything!{" "}
						</Heading>

						<div className="text-white flex flex-wrap items-center mt-4">
							<div className="flex items-center mb-2">
								<span className="shrink-0 mr-2">Powered by</span>
								<Select
									value={llm}
									onChange={(e) => {
										insertUrlParam("llm", e.target.value);
										setLlm(e.target.value);
									}}
									width={"240px"}
								>
									{/* <option value="anthropic_claude_3_opus">Anthropic-Claude-3-Opus</option> */}
									{/* <option value="openai_gpt_4_turbo_preview">GPT-4-Turbo</option> */}
									<option value="anthropic_claude_3_5_sonnet">Anthropic-Claude-3.5-Sonnet</option>
									<option value="anthropic_claude_3_7_sonnet">Anthropic-Claude-3.7-Sonnet</option>
									{/* <option value="openai_gpt_4o">GPT-4o</option> */}
									{/* <option value="openai_gpt_4o_mini">GPT-4o-mini</option>  */}
									{/* <option value="openai_gpt_3_5_turbo_1106">GPT-3.5-Turbo</option> */}
									{/* <option value="pplx_sonar_medium_chat">PPLX_sonar_medium_chat</option> */}
									{/* <option value="mistral_large">Mistral-Large</option> */}
									{/* <option value="command_r_plus">Command R+</option> */}
								</Select>
							</div>
						</div>
						<div className="ml-4">
							{showProcessingStatus(processingStatus)}
						</div>
					</Flex>
					<div
						className="flex flex-col-reverse w-full mb-2 overflow-y-auto overflow-x-hidden scroll-smooth bg-[#131318]"
						ref={messageContainerRef}
						style={{
							maxHeight: "calc(100vh - 420px)",
							minHeight: "200px",
							scrollBehavior: "smooth",
							flex: 1,
						}}
					>
						{
							[...messages]
								.reverse()
								.map((m, index) => (
									<ChatMessageBubble
										key={m.id}
										message={{ ...m }}
										aiEmoji="🦜"
										isMostRecent={index === 0}
										messageCompleted={!isLoading}
									></ChatMessageBubble>
								))
						}
					</div>
					{/* <ButtonGroup>
						{isShowSendEvmTx && <SendEVMTransaction txData={txDataEvm}></SendEVMTransaction>}
						{isShowSendSolTx && <SendSolanaTransaction txData={txDataSol} ></SendSolanaTransaction>}
						{isShowSendSolTxTW && <SendSolanaTransactionTW txData={txDataSolTW} ></SendSolanaTransactionTW>}
					</ButtonGroup> */}
					<InputGroup size="md" alignItems={"center"} className="w-full bg-[#131318] mb-8 sticky bottom-0 z-20 py-4 pb-8">
						<AutoResizeTextarea
							value={input}
							maxRows={5}
							// className="pr-24"
							marginRight={"1.5rem"}
							sx={{
								maxWidth: "100%",
								overflowX: "hidden",
								"&::-webkit-scrollbar": {
									width: "4px",
								},
								"&::-webkit-scrollbar-track": {
									background: "transparent",
								},
								"&::-webkit-scrollbar-thumb": {
									background: "gray.500",
									borderRadius: "2px",
								},
							}}
							placeholder="Hello, World!"
							textColor={"white"}
							borderColor={"rgb(58, 58, 61)"}
							onChange={(e) => setInput(e.target.value)}
							onKeyDown={(e) => {
								if (e.key === "Enter" && !e.shiftKey) {
									e.preventDefault();
									sendMessage();
								} else if (e.key === "Enter" && e.shiftKey) {
									e.preventDefault();
									setInput(input + "\n");
								}
							}}
						/>
						<InputRightElement width="auto" right="2" position="relative">
							<Flex gap={2}>
								<Tooltip label="Cancel" placement="top">
									<IconButton
										colorScheme="red"
										rounded={"full"}
										aria-label="Cancel"
										icon={<SmallCloseIcon />}
										onClick={handleCancel}
										isDisabled={!isLoading}
										_disabled={{
											opacity: 0.6,
											cursor: "not-allowed",
											bg: "gray.600",
											_hover: {
												bg: "gray.600"
											}
										}}
									/>
								</Tooltip>
								<Tooltip
									label="Upload files"
									placement="top"
								>
									<IconButton
										colorScheme={showUpload ? "gray" : "blue"}
										rounded={"full"}
										aria-label="Toggle file upload"
										icon={<Icon as={FaPlus} />}
										onClick={() => openFileUpload()}
										isDisabled={showUpload}
										_disabled={{
											opacity: 0.6,
											cursor: "not-allowed",
											bg: "gray.600",
											_hover: {
												bg: "gray.600"
											}
										}}
									/>
								</Tooltip>
								<IconButton
									colorScheme="blue"
									rounded={"full"}
									aria-label="Send"
									icon={isLoading ? <Spinner /> : <ArrowUpIcon />}
									type="submit"
									onClick={(e) => {
										e.preventDefault();
										sendMessage();
									}}
								/>
							</Flex>
						</InputRightElement>
					</InputGroup>
					{showUpload && <FileUploadArea
						imageFiles={imageFiles}
						imageUrls={imageUrls}
						pdfFiles={pdfFiles}
						onImageFilesChange={setImageFiles}
						onImageUrlsChange={setImageUrls}
						onPdfFilesChange={setPdfFiles}
						show={showUpload}
						onClose={() => setShowUpload(false)}
					/>}
				</div>
			</div >
		</div>
	);
}
