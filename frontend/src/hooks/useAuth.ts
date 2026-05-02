import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { getMe, googleLogin, login, logout, register } from "../lib/api";
import { useAuthStore } from "./useAuthStore";

export function useMe() {
  const setUser = useAuthStore((state) => state.setUser);
  return useQuery({
    queryKey: ["me"],
    queryFn: async () => {
      const me = await getMe();
      setUser(me);
      return me;
    },
    retry: false,
  });
}

export function useAuthActions() {
  const client = useQueryClient();
  const setUser = useAuthStore((state) => state.setUser);

  const loginMutation = useMutation({
    mutationFn: login,
    onSuccess: (result) => {
      setUser(result.user);
      client.invalidateQueries({ queryKey: ["me"] });
    },
  });

  const registerMutation = useMutation({
    mutationFn: register,
    onSuccess: (result) => {
      setUser(result.user);
      client.invalidateQueries({ queryKey: ["me"] });
    },
  });

  const googleMutation = useMutation({
    mutationFn: googleLogin,
    onSuccess: (result) => {
      setUser(result.user);
      client.invalidateQueries({ queryKey: ["me"] });
    },
  });

  const logoutMutation = useMutation({
    mutationFn: logout,
    onSuccess: () => {
      setUser(null);
      client.removeQueries({ queryKey: ["me"] });
      client.removeQueries({ queryKey: ["threads"] });
    },
  });

  return { loginMutation, registerMutation, googleMutation, logoutMutation };
}
