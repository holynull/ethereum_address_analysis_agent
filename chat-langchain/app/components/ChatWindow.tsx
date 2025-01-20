"use client";

import { Text, Tooltip } from "@chakra-ui/react";
import React, { useEffect, useRef, useState, useCallback } from "react";
import { EthereumProvider } from '@walletconnect/ethereum-provider';
import { ethers } from "ethers";
import { useSearchParams } from "next/navigation";
import { RemoteRunnable } from "langchain/runnables/remote";

import { ChatMessageBubble, Message } from "../components/ChatMessageBubble";
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
} from "@chakra-ui/react";
import { ArrowUpIcon, CloseIcon, Icon, SmallCloseIcon } from "@chakra-ui/icons";
import { Select } from "@chakra-ui/react";
import { Source } from "./SourceBubble";
import { AIMessageChunk } from "@langchain/core/messages"
import { FaCircleNotch, FaTools, FaKeyboard, FaCheck, FaLightbulb, FaPlus, FaWallet } from 'react-icons/fa';

import {
	UploadedImageFile,
	UploadedImageUrl,
	UploadedPDFFile
} from '../types/file';
import FileUploadArea from './FileUploadArea';
import GlobalPasteHint from './GlobalPasteHint';
import { ExternalProvider } from '@ethersproject/providers';
import { UniversalProvider, UniversalProviderOpts } from '@walletconnect/universal-provider';
import { SignClient } from '@walletconnect/sign-client';
import { error } from "console";

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
	const [account, setAccount] = useState<string>("");
	const [activeConnector, setActiveConnector] = useState<'metamask' | 'walletconnect' | null>(null);
	const [network, setNetwork] = useState<string>("");
	const [chainId, setChainId] = useState<string>("");
	const [isConnected, setIsConnected] = useState(false);
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

	// Initialize WalletConnect
	const [wcProvider, setWcProvider] = useState<any>(null);

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

	const connectWallet = async () => {
		if (wcProvider) {
			return
		}
		try {
			// If on mobile or MetaMask is not installed, use WalletConnect
			if (isMobile() || typeof window.ethereum === 'undefined') {
				// Initialize new WalletConnect if no active session
				const provider = await UniversalProvider.init({
					projectId: process.env.NEXT_PUBLIC_WALLET_CONNECT_PROJECT_ID || '', // your projectId
					metadata: {
						name: 'React App',
						description: 'React App for WalletConnect',
						url: 'https://walletconnect.com/',
						icons: ['https://avatars.githubusercontent.com/u/37784886']
					},
					client: undefined // optional instance of @walletconnect/sign-client
					// chains: [1, 56, 137], // mainnet
					// optionalChains: [5, 137, 80001], // goerli, polygon, mumbai
					// showQrModal: true,
				});
				// Register event listeners
				provider.on('connect', async () => {
					console.log("wallet connected.")
					const accounts = await provider.enable();
					if (accounts && accounts.length > 0) {
						setAccount(accounts[0]);
						setIsConnected(true);
						setActiveConnector('walletconnect');

						// Get network information
						const chainId = await provider.request({ method: 'eth_chainId' });
						const ethProvider = new ethers.providers.Web3Provider(provider);
						const network = await ethProvider.getNetwork();
						setChainId(chainId as string);
						setNetwork(network.name);
					}
				});

				provider.on('disconnect', () => {
					setIsConnected(false);
					setAccount('');
					setActiveConnector(null);
					setChainId("-1")
				});
				await provider.connect({
					optionalNamespaces: {
						eip155: {
							methods: [
								'eth_sendTransaction',
								'eth_signTransaction',
								'eth_sign',
								'personal_sign',
								'eth_signTypedData'
							],
							chains: ['eip155:1'],
							events: ['chainChanged', 'accountsChanged'],
							rpcMap: {
								80001:
									'https://rpc.walletconnect.com?chainId=eip155:80001&projectId=' + process.env.NEXT_PUBLIC_WALLET_CONNECT_PROJECT_ID
							}
						}
					},
					// pairingTopic: '<123...topic>', // optional topic to connect to
					// skipPairing: false // optional to skip pairing ( later it can be resumed by invoking .pair())
				});
				setWcProvider(provider);
			} else if (typeof window.ethereum !== 'undefined') {
				// Request account access
				const accounts = await window.ethereum.request({ method: 'eth_requestAccounts' });
				if (accounts && accounts.length > 0) {
					const currentAccount = accounts[0];
					setAccount(currentAccount);
					setIsConnected(true);
					setActiveConnector('metamask');

					// Create provider
					const provider = new ethers.providers.Web3Provider(window.ethereum);
					const network = await provider.getNetwork();
					const chainId = (await provider.getNetwork()).chainId.toString();
					setChainId(chainId);
					setNetwork(network.name);
					// You can do more with the provider here if needed
				}
			} else {
				//todo: If MetaMask not available, try WalletConnect

			}
		} catch (error) {
			console.error('Error connecting to wallet:\n' + error);
			setIsConnected(false);
			setAccount('');
			setActiveConnector(null);
			setChainId('-1');
			setNetwork('');
		}
	};

	// todo: Disconnect wallet function
	const disconnectWallet = async (isUnloading = false) => {
		try {
			console.log('[Wallet] Disconnecting wallet, isUnloading:', isUnloading);
			if (activeConnector === 'walletconnect' && wcProvider) {
				// Add a small delay to ensure the disconnect message is sent
				await Promise.race([
					wcProvider.disconnect(),
					new Promise(resolve => setTimeout(resolve, 1000))
				]);
			}
			setIsConnected(false);
			setAccount('');
			setActiveConnector(null);
			setChainId('-1');
			setNetwork('');
		} catch (error) {
			console.error('[Wallet] Error disconnecting wallet:', error);
		}
	};
	const CHAIN_CONFIG = {
		"1": {
			"chainId": "0x1",
			"chainName": "Ethereum Mainnet",
			"nativeCurrency": { "name": "Ether", "symbol": "ETH", "decimals": 18 },
			"rpcUrls": ["https://eth.public-rpc.com"],
			"blockExplorerUrls": ["https://etherscan.io"],
		},
		"56": {
			"chainId": "0x38",
			"chainName": "Binance Smart Chain",
			"nativeCurrency": { "name": "BNB", "symbol": "BNB", "decimals": 18 },
			"rpcUrls": ["https://bsc-dataseed.binance.org"],
			"blockExplorerUrls": ["https://bscscan.com"],
		},
		"137": {
			"chainId": "0x89",
			"chainName": "Polygon Mainnet",
			"nativeCurrency": { "name": "MATIC", "symbol": "MATIC", "decimals": 18 },
			"rpcUrls": ["https://polygon-rpc.com"],
			"blockExplorerUrls": ["https://polygonscan.com"],
		},
		"42161": {
			"chainId": "0xa4b1",
			"chainName": "Arbitrum One",
			"nativeCurrency": { "name": "Ethereum", "symbol": "ETH", "decimals": 18 },
			"rpcUrls": ["https://arb1.arbitrum.io/rpc"],
			"blockExplorerUrls": ["https://arbiscan.io"],
		},
		"10": {
			"chainId": "0xa",
			"chainName": "Optimism",
			"nativeCurrency": { "name": "Ethereum", "symbol": "ETH", "decimals": 18 },
			"rpcUrls": ["https://mainnet.optimism.io"],
			"blockExplorerUrls": ["https://optimistic.etherscan.io"],
		},
		"solana": {
			"chainId": "solana",
			"chainName": "Solana",
			"rpcUrls": ["https://api.mainnet-beta.solana.com"],
			"blockExplorerUrls": ["https://solscan.io"],
			"nativeCurrency": { "name": "SOL", "symbol": "SOL", "decimals": 9 },
			"isNonEVM": true
		}
	}

	const _change_network_to = async (chainId: string) => {
		const chainData = chainId === "solana" ? CHAIN_CONFIG["solana"] : CHAIN_CONFIG[chainId as keyof typeof CHAIN_CONFIG] as any;
		if (chainData.isNonEVM) {
			// 处理非EVM链切换
			if (chainData.chainId === "solana") {
				try {
					// 如果是WalletConnect
					if (activeConnector === 'walletconnect' && wcProvider) {
						await wcProvider.request({
							method: 'wallet_switchNetwork',
							params: [{ chainId: 'solana' }]
						});
					} else {
						// 如果是其他Solana钱包
						if (typeof window.solana !== 'undefined') {
							await window.solana.connect();
						} else {
							throw new Error('No Solana wallet found');
						}
					}
				} catch (error) {
					console.error('Error switching to Solana:', error);
					throw error;
				}
			}
		} else if (activeConnector === 'walletconnect' && wcProvider) {
			try {
				await wcProvider.request({
					method: 'wallet_switchEthereumChain',
					params: [{ chainId }],
				});
			} catch (switchError: any) {
				if (switchError.code === 4902) {
					await wcProvider.request({
						method: 'wallet_addEthereumChain',
						params: [chainData],
					});
				} else {
					console.log(switchError)
				}
			}
		} else if (typeof window.ethereum !== 'undefined') {
			try {
				if (typeof window.ethereum !== 'undefined') {
					// Try switching to network
					await window.ethereum.request({
						method: 'wallet_switchEthereumChain',
						params: [{ chainId }],
					});
				}
			} catch (switchError: any) {
				// Handle chain not added error
				if (switchError.code === 4902) {
					try {
						if (typeof window.ethereum !== 'undefined') {
							// Add the chain
							await window.ethereum.request({
								method: 'wallet_addEthereumChain',
								params: [chainData],
							});
						}
					} catch (addError) {
						console.error('Error adding chain:', addError);
					}
				} else {
					console.error('Error switching chain:', switchError);
				}
			}
		}
	}
	const change_network_to = async (network_data: any) => {
		if (Array.isArray(network_data) && network_data.length >= 2) {
			const chainId = network_data[1].chainId;
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
					input: messageValue,
					wallet_address: account,
					chain_id: chainId ? chainId.toString() : "-1",
					wallet_is_connected: isConnected,
					// chat_history: chatHistory,
					chat_history: [],
					image_urls: currentImages,
					pdf_files: currentPDFs,
				},
				{
					configurable: {
						llm: llmDisplayName,
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
									else
										console.log(_chunk)
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
										var _output = data.output as Array<any>
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
										var output = eval('(' + data.output + ')') as object;
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
										// 处理生成的图片数据
										const generatedImages = data.output as string[];
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
										const results = data.output as string[];
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
										const result = data.output as string;
										await connectWallet();
									}
								}
							}
							if ("name" in _chunk && _chunk.name == "change_network_to") {
								if ("data" in _chunk) {
									var data = _chunk.data as object;
									if ("output" in data) {
										const result = data.output as any;
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
							// }
							if ("name" in _chunk && (_chunk.name == "generate_transfer_native_token" || _chunk.name == "generate_approve_erc20" || _chunk.name == "generate_transfer_erc20_tx_data")) {
								if ("data" in _chunk) {
									var data = _chunk.data as object;
									if ("output" in data) {
										const result = data.output;
										// result example:
										// [
										// 	"Already notify the front end to sign the transaction data and send the transaction.",
										// 	{
										// 		"to": "0xdAC17F958D2ee523a2206206994597C13D831ec7",
										// 		"data": "0xa9059cbb0000000000000000000000003850c94a8a074111fbd17ad83239c9b099a68fa300000000000000000000000000000000000000000000000000000000002dc6c0"
										// 	}
										// ]
										// Send signed transaction using MetaMask signer
										try {
											if (Array.isArray(result) && result.length >= 2) {
												const txData = result[1] as any;
												// if (txData["chain_id"] != chainId) {
												// 	await _change_network_to(txData["chain_id"])
												// }
												// 根据当前连接器选择不同的provider
												// Get provider and signer
												let provider;
												if (activeConnector === 'walletconnect' && wcProvider) {
													provider = new ethers.providers.Web3Provider(wcProvider);
												} else if (typeof window.ethereum !== 'undefined') {
													provider = new ethers.providers.Web3Provider(window.ethereum as ExternalProvider);
													await provider.send("eth_requestAccounts", []);
												} else {
													throw new Error('No wallet provider found');
												}
												const signer = provider.getSigner(account);

												// Construct transaction object
												const transaction = {
													from: account,
													to: txData.to,
													data: txData.data,
													value: txData.value,
													gasLimit: txData.gasLimit,
													gasPrice: txData.gasPrice,
													chainId: txData.chain_id,
												};

												// Send transaction
												const tx = await signer.sendTransaction(transaction);
												console.log('Transaction hash:', tx.hash);

												// Wait for transaction confirmation
												// const receipt = await tx.wait();
												// console.log('Transaction confirmed:', receipt);

												// Add transaction result to message
												accumulatedMessage += `\nTransaction sent successfully! Hash: \`${tx.hash}\``;
											}
										} catch (error) {
											console.error('Transaction error:', error);
											// accumulatedMessage += `\nTransaction failed: ${error}`;
										}
									}
								}
							}
							if ("name" in _chunk && (_chunk.name == "generate_swap_tx_data")) {
								if ("data" in _chunk) {
									var data = _chunk.data as object;
									if ("output" in data) {
										const result = data.output as any;
										if (result["success"]) {
											const swap_data = result["swap_data"] as any;
											if (!swap_data.chain_type) {
												throw new Error("Missing chain_type in swap data");
											}
											let signedTx = null;
											if (swap_data.chain_type === "evm") {
												try {
													// if (txData["chain_id"] != chainId) {
													// 	await _change_network_to(txData["chain_id"])
													// }
													// 根据当前连接器选择不同的provider
													// Get provider and signer
													let provider;
													if (activeConnector === 'walletconnect' && wcProvider) {
														provider = new ethers.providers.Web3Provider(wcProvider);
													} else if (typeof window.ethereum !== 'undefined') {
														provider = new ethers.providers.Web3Provider(window.ethereum as ExternalProvider);
														await provider.send("eth_requestAccounts", []);
													} else {
														throw new Error('No wallet provider found');
													}
													const signer = provider.getSigner(account);
													// Construct transaction object
													const transaction = {
														from: account,
														to: swap_data.txData.to,
														data: swap_data.txData.data,
														value: swap_data.txData.value,
														gasLimit: swap_data.gasLimit,
														gasPrice: swap_data.gasPrice,
														chainId: swap_data.chain_id,
													};

													// Send transaction
													signedTx = await signer.sendTransaction(transaction);


													// Wait for transaction confirmation
													// const receipt = await tx.wait();
													// console.log('Transaction confirmed:', receipt);

													// Add transaction result to message
													accumulatedMessage += `\nTransaction sent successfully! Hash: \`${signedTx.hash}\``;
												} catch (error) {
													console.error('Transaction error:', error);
													// accumulatedMessage += `\nTransaction failed: ${error}`;
												}
												if (signedTx) {
													console.log('Transaction hash:', signedTx.hash);
													// Generate order record after transaction is sent
													try {
														const orderInfo = result.order_info;
														await fetch(process.env.NEXT_PUBLIC_API_URL + '/generate_swap_order', {
															method: 'POST',
															headers: { 'Content-Type': 'application/json' },
															body: JSON.stringify({
																hash: signedTx.hash,
																from_token_address: orderInfo.from_token_address,
																to_token_address: orderInfo.to_token_address,
																from_address: orderInfo.from_address,
																to_address: orderInfo.to_address,
																from_token_chain: orderInfo.from_token_chain,
																to_token_chain: orderInfo.to_token_chain,
																from_token_amount: orderInfo.from_token_amount,
																amount_out_min: orderInfo.amount_out_min,
																from_coin_code: orderInfo.from_coin_code,
																to_coin_code: orderInfo.to_coin_code,
																source_type: orderInfo.source_type,
																slippage: orderInfo.slippage
															})
														});
														console.log("Update order info success.")
													} catch (error) {
														console.error('Error generating swap order:', error);
														accumulatedMessage += '\nFailed to generate swap order record.';
													}
												}
											} else if (swap_data.chain_type === "solana") {
												try {
													const signClient = await SignClient.init({
														projectId: process.env.NEXT_PUBLIC_WALLET_CONNECT_PROJECT_ID || '', // your projectId
													});
													const session = await signClient.connect({
														requiredNamespaces: {
															solana: {
																methods: ['solana_signTransaction'],
																chains: ['solana:mainnet'],
																events: ['connect', 'disconnect']
															}
														}
													});
													// Get tx and signer data from txData for Solana
													const { tx, signer } = swap_data.txData;

													// Use WalletConnect to sign Solana transaction
													signedTx = await signClient.request({
														topic: (session as any).topic,
														chainId: "solana:mainnet",
														request: {
															method: "solana_signTransaction",
															params: {
																transaction: tx,
																signer: signer
															}
														}
													});

													// Handle transaction result
													// if (signedTx) {
													// 广播交易
													// const signature = await signClient.sendRawTransaction(signedTx);
													// 	console.log('Solana transaction signed:', signedTx);
													// 	accumulatedMessage += `\nSolana transaction signed successfully! Hash: \`${signedTx.hash}\``;
													// }
												} catch (error) {
													console.error('Solana transaction error:', error);
													accumulatedMessage += `\nFailed to sign Solana transaction: ${error}`;
												}
											} else {
												console.error('Unsupported chain type:', swap_data.chain_type);
												accumulatedMessage += `\nUnsupported chain type: ${swap_data.chain_type}`;
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
									});
								} else if (newMessages[messageIndex] !== undefined) {
									// newMessages[messageIndex].content = parsedResult.trim();
									newMessages[messageIndex].runId = runId;
									newMessages[messageIndex].sources = sources;
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
					setAccount(accounts[0]);
					setIsConnected(true);

					// Get current network
					const provider = new ethers.providers.Web3Provider(window.ethereum as ExternalProvider);
					const network = await provider.getNetwork();
					const chainId = network.chainId.toString();
					setChainId(chainId);
					setNetwork(network.name);
				}
			} catch (error) {
				console.error('Error checking wallet connection:', error);
			}
		}
	};

	// Check wallet connection on component mount
	useEffect(() => {
		// Add multiple event listeners for cleanup
		const handleBeforeUnload = async () => {
			// Call disconnectWallet before unloading
			console.log('[Wallet] beforeunload event triggered');
			await disconnectWallet(true);
		};
		// Monitor page visibility changes
		const handleVisibilityChange = async () => {
			if (document.visibilityState === 'hidden') {
				console.log('[Wallet] Page visibility changed to hidden');
				// await disconnectWallet(true);
			}
		};

		// Add event listeners
		window.addEventListener('beforeunload', () => {
			handleBeforeUnload(); setTimeout(() => {

			}, 500);
		});
		document.addEventListener('visibilitychange', handleVisibilityChange);
		// Initial setup and checks
		checkWalletConnection();

		// Setup WalletConnect listeners if provider exists
		if (wcProvider) {
			wcProvider.on('connect', async () => {
				const accounts = await wcProvider.enable();
				if (accounts && accounts.length > 0) {
					setAccount(accounts[0]);
					setIsConnected(true);
					setActiveConnector('walletconnect');

					// Get network information
					const chainId = await wcProvider.request({ method: 'eth_chainId' });
					const provider = new ethers.providers.Web3Provider(wcProvider);
					const network = await provider.getNetwork();
					setChainId(chainId);
					setNetwork(network.name);
				}
			});

			wcProvider.on('disconnect', () => {
				setIsConnected(false);
				setAccount('');
				setActiveConnector(null);
				setChainId('-1');
				setNetwork('');
			});

			wcProvider.on('chainChanged', async (chainId: string) => {
				const provider = new ethers.providers.Web3Provider(wcProvider);
				const network = await provider.getNetwork();
				setChainId(parseInt(chainId, 16).toString());
				setNetwork(network.name);
			});
			wcProvider.on('accountsChanged', (accounts: string[]) => {
				if (accounts.length === 0) {
					// Wallet disconnected
					setIsConnected(false);
					setAccount('');
				} else {
					setAccount(accounts[0]);
					setIsConnected(true);
				}
			});
		}
		// todo: Setup WalletConnect event listeners

		if (typeof window.ethereum !== 'undefined') {
			// Listen for chain changes
			window.ethereum.on('chainChanged', async () => {
				const provider = new ethers.providers.Web3Provider(window.ethereum as ExternalProvider);
				const network = await provider.getNetwork();
				const chainId = network.chainId.toString();
				setChainId(parseInt(chainId, 16).toString());
				setNetwork(network.name);
			});
			window.ethereum.on('accountsChanged', (accounts: string[]) => {
				if (accounts.length === 0) {
					// Wallet disconnected
					setIsConnected(false);
					setAccount('');
				} else {
					setAccount(accounts[0]);
					setIsConnected(true);
				}
			});
		}

		return () => {
			// Remove WalletConnect listeners
			if (wcProvider) {
				wcProvider.removeListener('connect', () => { });
				wcProvider.removeListener('disconnect', () => { });
				wcProvider.removeListener('chainChanged', () => { });
			}


			// Remove MetaMask listeners
			if (typeof window.ethereum !== 'undefined') {
				window.ethereum.removeListener('accountsChanged', () => { });
				window.ethereum.removeListener('chainChanged', () => { });
			}
			// Remove beforeunload event listener
			// Remove all event listeners
			window.addEventListener('beforeunload', () => {
				handleBeforeUnload(); setTimeout(() => {

				}, 500);
			});
			document.removeEventListener('visibilitychange', handleVisibilityChange);
			// Disconnect wallet on component unmount
			// disconnectWallet(true);
		};
	}, [wcProvider]);

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
			{showPasteHint && <GlobalPasteHint onClose={handleClosePasteHint} />}
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
										`Connected via ${activeConnector === 'metamask' ? 'MetaMask' : 'WalletConnect'}: ${network} (Chain ID: ${chainId}) - ${account}` :
										'Connect Wallet'}
									placement="top">
									{isConnected ? (
										<IconButton
											colorScheme="green"
											rounded={"full"}
											aria-label="Disconnect Wallet"
											icon={<Icon as={FaWallet} />}
											onClick={() => disconnectWallet()}
										/>
									) : (
										<IconButton
											colorScheme="red"
											rounded={"full"}
											aria-label="Connect MetaMask"
											icon={<Icon as={FaWallet} />}
											onClick={() => { connectWallet() }}
										/>
									)}
								</Tooltip>
							</Box>
							Ξ Musse AI Assistant 💼
						</Heading>
						{isMobile() && isConnected && (
							<div className="text-white text-sm mt-2 text-center px-4">
								<div>Network: {network} (Chain ID: {chainId})</div>
								<div className="mt-1 opacity-80 break-all">{account}</div>
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
									<option value="openai_gpt_4o">GPT-4o</option>
									<option value="openai_gpt_4o_mini">GPT-4o-mini</option>
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
