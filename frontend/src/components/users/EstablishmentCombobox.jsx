import React, { useState } from 'react';
import { ChevronsUpDown } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from '@/components/ui/command';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';

/**
 * Establecimiento con búsqueda por RBD o nombre. No existe `Combobox` en el estilo `default`
 * de shadcn: se arma con Popover + Command, como indica el skill.
 */
export default function EstablishmentCombobox({ id, establishments, value, onChange, invalid = false }) {
  const [open, setOpen] = useState(false);
  const selected = establishments.find((e) => e.rbd === value);
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button id={id} type="button" variant="outline" role="combobox" aria-expanded={open} aria-invalid={invalid || undefined}
          className="w-full justify-between font-normal">
          <span className="truncate">{selected ? `${selected.name} · RBD ${selected.rbd}` : 'Buscar por RBD o nombre'}</span>
          <ChevronsUpDown data-icon="inline-end" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[--radix-popover-trigger-width] p-0" align="start">
        <Command>
          <CommandInput placeholder="RBD o nombre del establecimiento" />
          <CommandList>
            <CommandEmpty>No hay establecimientos con ese criterio.</CommandEmpty>
            <CommandGroup>
              {establishments.map((e) => (
                <CommandItem key={e.rbd} value={`${e.rbd} ${e.name} ${e.comuna ?? ''}`} onSelect={() => { onChange(e.rbd); setOpen(false); }}>
                  <span className="truncate">{e.name}</span>
                  <span className="ml-auto text-xs text-muted-foreground">RBD {e.rbd}</span>
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
