import { AppProps } from 'next/app';
import '../app/globals.css';
import { useEffect } from 'react';
import { createAppKit } from '@reown/appkit';
import { SolanaAdapter } from '@reown/appkit-adapter-solana';
import { EthersAdapter } from '@reown/appkit-adapter-ethers';
import { solana, solanaTestnet, solanaDevnet } from '@reown/appkit/networks';
import { mainnet, bsc, tron, arbitrum, sepolia } from '@reown/appkit/networks';
import { SolflareWalletAdapter, PhantomWalletAdapter } from '@solana/wallet-adapter-wallets';

function MyApp({ Component, pageProps }: AppProps) {
  useEffect(() => {
    // Initialize AppKit when the app mounts
    const ethersAdapter = new EthersAdapter();
    const solanaWeb3JsAdapter = new SolanaAdapter({
      wallets: [new PhantomWalletAdapter(), new SolflareWalletAdapter()]
    });

    createAppKit({
      adapters: [ethersAdapter, solanaWeb3JsAdapter],
      networks: [mainnet, bsc, tron, arbitrum, sepolia, solana, solanaTestnet, solanaDevnet],
      projectId: process.env.NEXT_PUBLIC_WALLET_CONNECT_PROJECT_ID || '',
      metadata: {
        name: 'Musse AI',
        description: 'Musse AI',
        url: typeof window !== 'undefined' ? window.location.origin : '',
        icons: ['https://yourapp.com/icon.png'],
      },
      features: {
        analytics: true,
      }
    });
  }, []); // Empty dependency array means this runs once on mount

  return <Component {...pageProps} />;
}

export default MyApp;
