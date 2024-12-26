interface EthereumProvider {
    request: (args: { method: string; params?: any[] }) => Promise<any>;
    on: (eventName: string, callback: (...args: any[]) => void) => void;
    removeListener: (eventName: string, callback: (...args: any[]) => void) => void;
    selectedAddress: string | null;
    isMetaMask?: boolean;
    chainId?: string;
}

declare global {
    interface Window {
        ethereum?: EthereumProvider;
    }
}

export {};